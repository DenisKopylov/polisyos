"""Behavioral contract for the Foundry-owned N8 dependency identity."""

from __future__ import annotations

import ast
import gc
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import tomllib
import weakref
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Barrier, RLock, Thread
from typing import Annotated, Literal, cast

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    Ed25519Signer,
    Ed25519Verifier,
    FileSystemCAS,
    KeyPair,
    PutOptions,
)
from polisyos.foundry.methods.catalog import dependency_authority as authority_module
from polisyos.foundry.methods.catalog import dependency_profile as profile_module
from polisyos.foundry.methods.catalog.dependency_authority import (
    AbsoluteRequestPath,
    AuthorityFailureCode,
    AuthorityPredicateId,
    MethodCatalogDependencyAuthorityRequest,
    NegativeDependencyAuthorityResultKind,
    UnestablishedMethodCatalogDependencyProfile,
    build_production_method_catalog_dependency_authority,
)
from polisyos.foundry.methods.catalog.dependency_evidence import (
    BidirectionalAuthorityPredicateSpec,
    BidirectionalUnestablishedAuthorityPredicate,
    DigestDomain,
    DigestPredicateMismatch,
    DigestPreimageKind,
    DomainDigest,
    DomainEvidenceRequirement,
    DomainScalar,
    FoundryAuthorityModel,
    GitCommitRelation,
    MissingEvidenceDomainsRequirement,
    ProductionDataTrustPolicyStatement,
    RejectedAuthorityPredicate,
    RevocationCutoffDisposition,
    RootedRelativePath,
    SatisfiedAuthorityPredicate,
    ScalarDomain,
    ScalarPredicateMismatch,
    TrustPublicKey,
    TrustRevocationStatement,
    TrustRole,
    canonical_json_bytes,
    decode_digest_domain_registry_toml,
    domain_digest,
    record_ref,
)
from polisyos.foundry.methods.catalog.dependency_profile import (
    DependencyProfileEnvironmentReceipt,
    MethodCatalogDependencyProfileDeclaration,
    MethodCatalogProfileAdmission,
    ProductionDataManifestMissingFailure,
    ProductionDataManifestPresent,
    ProductionDataManifestUnavailable,
    ResolvedMethodCatalogDependencyProfile,
    declaration_ref,
    load_dependency_profile_registry,
    read_candidate_production_data_manifest,
    reconcile_bound_installed_environment,
    resolve_dependency_profile,
    resolve_profile_declaration,
)
from tools.quality.validation import check_layer3_gy_epoch_chronology_contract as chronology
from tools.quality.validation import check_layer3_gy_second_domain_pack as n10a
from tools.quality.validation import check_layer3_gy_value_gate_contract as n8

_PRODUCT_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_REGISTRY = (
    _PRODUCT_ROOT
    / "architecture"
    / "production_quality"
    / "method_catalog_dependency_profiles.toml"
)
_DIGEST_REGISTRY = (
    _PRODUCT_ROOT
    / "architecture"
    / "production_quality"
    / "method_catalog_dependency_digest_domains.toml"
)

_EXPECTED_DOMAINS_BY_PREIMAGE_KIND = {
    DigestPreimageKind.CANONICAL_STATEMENT: frozenset(
        {
            DigestDomain.CANONICAL_SOURCE,
            DigestDomain.PROFILE_DECLARATION,
            DigestDomain.PROFILE_ADMISSION,
            DigestDomain.TOOLCHAIN_RUNTIME,
            DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED,
            DigestDomain.TOOLCHAIN_RUNTIME_ROOT,
            DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN,
            DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION,
            DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION,
            DigestDomain.TRUST_MATERIAL,
            DigestDomain.TRUST_REVOCATION,
            DigestDomain.TRUST_RESOLUTION,
            DigestDomain.TRUST_POLICY,
            DigestDomain.VERIFIER_PROVENANCE,
            DigestDomain.PRODUCTION_APPOINTMENT,
            DigestDomain.PRODUCTION_CUSTODY,
            DigestDomain.ROOT_CHALLENGE,
            DigestDomain.ROOT_MOUNT_RESOLUTION,
            DigestDomain.ROOT_ACCESS,
            DigestDomain.SELECTED_DISTRIBUTION,
            DigestDomain.WHEEL_RECORD,
            DigestDomain.SOURCE_TREE,
            DigestDomain.BUILD_PROFILE,
            DigestDomain.BUILD_LINEAGE,
            DigestDomain.ENVIRONMENT_MARKER,
            DigestDomain.ENVIRONMENT_RECEIPT,
            DigestDomain.CAPSULE,
            DigestDomain.RESOLUTION_REQUEST,
            DigestDomain.SIGNED_EVIDENCE,
        }
    ),
    DigestPreimageKind.RAW_BLOB: frozenset(
        {
            DigestDomain.RAW_BLOB,
            DigestDomain.PYPROJECT,
            DigestDomain.UV_LOCK,
            DigestDomain.TOOLCHAIN_SELECTED,
            DigestDomain.TOOLCHAIN_EXECUTABLE,
            DigestDomain.TOOLCHAIN_RUNTIME_ROOT_PATH,
            DigestDomain.PRODUCTION_MANIFEST,
            DigestDomain.ROOT_NONCE,
            DigestDomain.ROOT_MOUNT_REQUEST,
            DigestDomain.LOCKED_SOURCE,
            DigestDomain.SELECTED_WHEEL,
            DigestDomain.SELECTED_SOURCE,
            DigestDomain.BUILD_ARGV,
            DigestDomain.BUILD_ENVIRONMENT,
            DigestDomain.ENVIRONMENT_INSTANCE,
            DigestDomain.VERIFIER_APPOINTMENT,
        }
    ),
    DigestPreimageKind.TRACKED_TOML: frozenset(
        {
            DigestDomain.PROFILE_REGISTRY,
            DigestDomain.AUTHORITY_REGISTRY,
            DigestDomain.DIGEST_REGISTRY,
        }
    ),
    DigestPreimageKind.ORDERED_ROWS: frozenset(
        {
            DigestDomain.INSTALLED_STABLE,
            DigestDomain.INSTALLED_INSTANCE,
            DigestDomain.DISTRIBUTION_SET,
            DigestDomain.CONTENT_SET_STABLE,
            DigestDomain.CONTENT_SET_INSTANCE,
        }
    ),
    DigestPreimageKind.RELATION: frozenset(
        {
            DigestDomain.TOOLCHAIN_RUNTIME_BINDING,
            DigestDomain.INSTALLED_BINDING,
            DigestDomain.DEPENDENCY_DISCRIMINANT,
            DigestDomain.DEPENDENCY_CLOSURE,
            DigestDomain.DERIVED_UV_ARGV,
            DigestDomain.SIGNED_RECORD_BINDING,
            DigestDomain.SIGNED_BINDING_INDEX,
        }
    ),
}


@pytest.fixture(autouse=True)
def _isolate_polisyos_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep catalog caches out of the appointed hermetic tooling home."""

    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "polisyos-cache").as_posix())


def _current_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _authority_request(
    tmp_path: Path,
    *,
    source_freeze: str | None = None,
) -> MethodCatalogDependencyAuthorityRequest:
    return MethodCatalogDependencyAuthorityRequest(
        authority_purpose="n8_method_catalog_reconstruction",
        expected_source_freeze_commit=source_freeze or _current_commit(),
        production_data_root=AbsoluteRequestPath(value=tmp_path / "production-data"),
        environment_root=AbsoluteRequestPath(value=tmp_path / "environment"),
    )


def _git_at(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _install_clean_source_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, Path, str]:
    repo_root = tmp_path / "repo"
    product_root = repo_root / "policy-engine"
    source_git_root = _PRODUCT_ROOT.parent
    for relative_path in authority_module._AUTHORITY_SOURCE_PATHS:
        source = source_git_root / relative_path
        destination = repo_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    _git_at(repo_root, "init", "-b", "fixture")
    _git_at(repo_root, "config", "user.name", "GY-N12 test")
    _git_at(repo_root, "config", "user.email", "gy-n12@example.invalid")
    _git_at(repo_root, "add", "--", "policy-engine")
    _git_at(repo_root, "commit", "-m", "fixture source")
    source_freeze = _git_at(repo_root, "rev-parse", "HEAD")
    monkeypatch.setattr(authority_module, "_GIT_ROOT", repo_root)
    monkeypatch.setattr(authority_module, "_PRODUCT_ROOT", product_root)
    quality_root = product_root / "architecture" / "production_quality"
    monkeypatch.setattr(
        authority_module,
        "_PROFILE_REGISTRY_PATH",
        quality_root / "method_catalog_dependency_profiles.toml",
    )
    monkeypatch.setattr(
        authority_module,
        "_AUTHORITY_REGISTRY_PATH",
        quality_root / "method_catalog_dependency_authority.toml",
    )
    monkeypatch.setattr(
        authority_module,
        "_DIGEST_REGISTRY_PATH",
        quality_root / "method_catalog_dependency_digest_domains.toml",
    )
    return repo_root, product_root, source_freeze


def _marker_environment() -> dict[str, str]:
    return {
        "extra": "",
        "implementation_name": "cpython",
        "implementation_version": "3.14.0",
        "os_name": "posix",
        "platform_machine": "arm64",
        "platform_python_implementation": "CPython",
        "platform_system": "Darwin",
        "python_full_version": "3.14.0",
        "python_version": "3.14",
        "sys_platform": "darwin",
    }


@dataclass(frozen=True, slots=True)
class _SyntheticOwnerPayload:
    value: str


@dataclass(slots=True)
class _SyntheticOwnerResource:
    key: int
    closed: bool = False
    fail_close: bool = False
    fail_key: bool = False

    def require_current_process_descriptor(self) -> int:
        if self.closed:
            raise OSError("closed synthetic owner resource")
        return self.key

    def owner_resource_lease_key(self) -> tuple[Literal["synthetic"], int, int]:
        if self.fail_key:
            raise OSError("synthetic lease-key failure")
        return ("synthetic", os.getpid(), self.key)

    def close_owner_resource(self) -> None:
        self.closed = True
        if self.fail_close:
            raise OSError("synthetic disposal failed")


@dataclass(slots=True)
class _SyntheticResourcePayload:
    resource: _SyntheticOwnerResource


def _construct_owner_kernel(
    specs: tuple[authority_module._OwnerPayloadSpec[object, object], ...],
) -> tuple[object, object, object]:
    lock = RLock()

    @contextmanager
    def lifecycle() -> object:
        with lock:
            yield

    def claim(**_kwargs: object) -> authority_module._OwnerResourceClaim:
        return authority_module._OwnerResourceClaim(lease=object(), resources=())

    return authority_module._build_owner_capability_kernel(
        specs,
        claim_owner_resources=claim,
        release_owner_resources=lambda _claim: None,
        register_fork_participant=lambda _participant: None,
        lifecycle_section=lifecycle,
    )


def _build_synthetic_owner_kernel(
    *,
    claim: object | None = None,
    release: object | None = None,
) -> tuple[
    tuple[authority_module._OwnerPayloadSpec[object, object], ...],
    object,
    object,
    object,
    list[object],
]:
    token_types = tuple(
        authority_module._fieldless_owner_token(
            type(f"SyntheticToken{index}", (), {})
        )
        for index, _kind in enumerate(authority_module.OwnerCapabilityKind)
    )
    specs = tuple(
        authority_module._OwnerPayloadSpec(
            kind=kind,
            token_type=token_type,
            payload_type=_SyntheticOwnerPayload,
            exact_concrete_leaves=(),
            dynamic_record_domain_path=None,
            dynamic_record_ref_domain_path=None,
            child_resource_paths=(),
            nested_tokens=(),
        )
        for kind, token_type in zip(
            authority_module.OwnerCapabilityKind,
            token_types,
            strict=True,
        )
    )
    lock = RLock()
    participants: list[object] = []

    @contextmanager
    def lifecycle() -> object:
        with lock:
            yield

    def no_resources(**_kwargs: object) -> authority_module._OwnerResourceClaim:
        return authority_module._OwnerResourceClaim(lease=object(), resources=())

    mint, unwrap, release_token = authority_module._build_owner_capability_kernel(
        specs,
        claim_owner_resources=claim or no_resources,  # type: ignore[arg-type]
        release_owner_resources=release or (lambda _claim: None),  # type: ignore[arg-type]
        register_fork_participant=participants.append,
        lifecycle_section=lifecycle,
    )
    return specs, mint, unwrap, release_token, participants


def _build_resource_backed_owner_kernel(
    *,
    on_claim: object | None = None,
) -> tuple[
    tuple[authority_module._OwnerPayloadSpec[object, object], ...],
    object,
    object,
    object,
    dict[tuple[str, int, int], object],
]:
    token_types = tuple(
        authority_module._fieldless_owner_token(
            type(f"ResourceToken{index}", (), {})
        )
        for index, _kind in enumerate(authority_module.OwnerCapabilityKind)
    )
    specs: tuple[authority_module._OwnerPayloadSpec[object, object], ...] = tuple(
        authority_module._OwnerPayloadSpec(
            kind=kind,
            token_type=token_type,
            payload_type=(
                _SyntheticResourcePayload
                if index == 0
                else _SyntheticOwnerPayload
            ),
            exact_concrete_leaves=(
                (
                    authority_module._OwnerPayloadLeafSpec(
                        ("resource",),
                        _SyntheticOwnerResource,
                    ),
                )
                if index == 0
                else ()
            ),
            dynamic_record_domain_path=None,
            dynamic_record_ref_domain_path=None,
            child_resource_paths=(("resource",),) if index == 0 else (),
            nested_tokens=(),
        )
        for index, (kind, token_type) in enumerate(
            zip(authority_module.OwnerCapabilityKind, token_types, strict=True)
        )
    )
    lock = RLock()
    leases: dict[tuple[str, int, int], object] = {}

    @contextmanager
    def lifecycle() -> object:
        with lock:
            yield

    def claim(
        *,
        capability_kind: authority_module.OwnerCapabilityKind,
        resources: tuple[_SyntheticOwnerResource, ...],
    ) -> authority_module._OwnerResourceClaim:
        rows = tuple((resource.owner_resource_lease_key(), resource) for resource in resources)
        if any(key in leases for key, _resource in rows):
            raise authority_module.OwnerCapabilityFault(
                code=authority_module.OwnerCapabilityFaultCode.RESOURCE_ALREADY_OWNED,
                disposition=authority_module.OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=capability_kind,
            )
        lease = object()
        for key, _resource in rows:
            leases[key] = lease
        if on_claim is not None:
            on_claim(resources)  # type: ignore[operator]
        return authority_module._OwnerResourceClaim(
            lease=lease,
            resources=rows,  # type: ignore[arg-type]
        )

    def release(claim: authority_module._OwnerResourceClaim) -> None:
        for key, resource in claim.resources:
            if leases.get(key) is claim.lease:
                leases.pop(key)
            resource.close_owner_resource()

    mint, unwrap, release_token = authority_module._build_owner_capability_kernel(
        specs,
        claim_owner_resources=claim,  # type: ignore[arg-type]
        release_owner_resources=release,
        register_fork_participant=lambda _participant: None,
        lifecycle_section=lifecycle,
    )
    return specs, mint, unwrap, release_token, leases


def _admission(
    declaration: MethodCatalogDependencyProfileDeclaration,
) -> MethodCatalogProfileAdmission:
    return MethodCatalogProfileAdmission(
        schema_version="polisyos.foundry.profile-admission.v1",
        authority_purpose="n8_method_catalog_reconstruction",
        profile_id=declaration.profile_id,
        declaration_ref=declaration_ref(declaration),
        python_runtime_ref=record_ref(
            DigestDomain.TOOLCHAIN_RUNTIME,
            b"candidate-python-runtime",
            schema_version="polisyos.foundry.python-runtime-manifest.v1",
        ),
        uv_executable_ref=record_ref(
            DigestDomain.TOOLCHAIN_EXECUTABLE,
            b"candidate-uv-executable",
            schema_version="polisyos.foundry.executable-blob.v1",
        ),
        production_data_trust_policy_ref=record_ref(
            DigestDomain.TRUST_POLICY,
            b"candidate-production-data-trust-policy",
            schema_version="polisyos.foundry.production-data-trust-policy.v1",
        ),
        predicate_class="recomputed",
    )


def _resolve_tracked_profile() -> ResolvedMethodCatalogDependencyProfile:
    declaration = load_dependency_profile_registry(_PROFILE_REGISTRY).declarations[0]
    result = resolve_dependency_profile(
        declaration,
        pyproject_bytes=(_PRODUCT_ROOT / "pyproject.toml").read_bytes(),
        lockfile_bytes=(_PRODUCT_ROOT / "uv.lock").read_bytes(),
        marker_environment=_marker_environment(),
        production_data_manifest=ProductionDataManifestPresent(
            kind="present",
            exact_bytes=b"{}",
        ),
        admission=_admission(declaration),
    )
    assert isinstance(result, ResolvedMethodCatalogDependencyProfile)
    return result


@dataclass(frozen=True, slots=True)
class _ExactEnvironmentEvidence:
    blobs: dict[str, bytes]

    def read_blob(
        self,
        *,
        record_ref: authority_module.FoundryRecordRef[DigestDomain],
    ) -> bytes:
        try:
            return self.blobs[record_ref.artifact_id]
        except KeyError as exc:
            raise FileNotFoundError(record_ref.artifact_id) from exc


@dataclass(frozen=True, slots=True)
class _CandidateEnvironmentFixture:
    root: Path
    marker: authority_module.evidence_module.DependencyEnvironmentMarkerStatement
    marker_raw: bytes
    receipt: DependencyProfileEnvironmentReceipt
    evidence: _ExactEnvironmentEvidence


def _selected_distribution_ref(
    row: object,
    *,
    label: str,
) -> authority_module.FoundryRecordRef[
    Literal[DigestDomain.SELECTED_DISTRIBUTION]
]:
    selected = row.selected_artifact
    candidate = record_ref(
        DigestDomain.SELECTED_DISTRIBUTION,
        label.encode("utf-8"),
        schema_version="polisyos.foundry.selected-distribution.v1",
    )
    return authority_module.FoundryRecordRef[
        Literal[DigestDomain.SELECTED_DISTRIBUTION]
    ](
        artifact_id=candidate.artifact_id,
        semantic_hash=selected,
        schema_version=candidate.schema_version,
    )


def _candidate_environment_fixture(
    tmp_path: Path,
    profile: ResolvedMethodCatalogDependencyProfile,
    *,
    label: str,
    selected_overrides: dict[str, tuple[str, DomainDigest[DigestDomain]]] | None = None,
    extra_distributions: tuple[
        authority_module.evidence_module.InstalledDistributionIdentity, ...
    ] = (),
    admission_ref: authority_module.FoundryRecordRef[
        Literal[DigestDomain.PROFILE_ADMISSION]
    ]
    | None = None,
    write_marker: bool = True,
    sync_root_access_ref: authority_module.FoundryRecordRef[
        Literal[DigestDomain.ROOT_ACCESS]
    ]
    | None = None,
    sync_root_access_binding_ref: authority_module.FoundryRecordRef[
        Literal[DigestDomain.SIGNED_RECORD_BINDING]
    ]
    | None = None,
    python_runtime_ref: authority_module.FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME]
    ]
    | None = None,
    runtime_installation_ref: authority_module.FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]
    ]
    | None = None,
    runtime_verification_ref: authority_module.FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION]
    ]
    | None = None,
) -> _CandidateEnvironmentFixture:
    overrides = selected_overrides or {}
    observed = []
    for row in profile.distributions:
        version, selected = overrides.get(
            row.name,
            (row.version, row.selected_artifact),
        )
        selected_ref = _selected_distribution_ref(row, label=f"{label}:{row.name}")
        if selected != row.selected_artifact:
            selected_ref = selected_ref.model_copy(update={"semantic_hash": selected})
        observed.append(
            authority_module.evidence_module.InstalledDistributionIdentity(
                normalized_name=row.name,
                version=version,
                selected_artifact_ref=selected_ref,
                observed_stable_manifest_ref=_c1_ref(
                    DigestDomain.INSTALLED_STABLE,
                    f"{label}:stable:{row.name}",
                ),
                observed_instance_manifest_ref=_c1_ref(
                    DigestDomain.INSTALLED_INSTANCE,
                    f"{label}:instance:{row.name}",
                ),
                observed_source_binding_ref=_c1_ref(
                    DigestDomain.INSTALLED_BINDING,
                    f"{label}:binding:{row.name}",
                ),
            )
        )
    runtime_installation_ref = runtime_installation_ref or _c1_ref(
        DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION,
        f"{label}:runtime-installation",
    )
    runtime_verification_ref = runtime_verification_ref or _c1_ref(
        DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION,
        f"{label}:runtime-verification",
    )
    instance_content_set = domain_digest(
        DigestDomain.CONTENT_SET_INSTANCE,
        f"{label}:instance-content".encode(),
    )
    marker = authority_module.evidence_module.DependencyEnvironmentMarkerStatement(
        schema_version="polisyos.foundry.dependency-environment-marker.v1",
        environment_creation_nonce=domain_digest(
            DigestDomain.ENVIRONMENT_INSTANCE,
            label.encode(),
        ),
        stable_closure=profile.stable_closure,
        source_authority_ref=_c1_ref(DigestDomain.CANONICAL_SOURCE, f"{label}:source"),
        python_runtime_ref=python_runtime_ref or profile.admission.python_runtime_ref,
        python_runtime_installation_ref=runtime_installation_ref,
        observed_python_runtime_ref=_c1_ref(
            DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED,
            f"{label}:runtime-observed",
        ),
        python_runtime_verification_ref=runtime_verification_ref,
        uv_executable_ref=profile.admission.uv_executable_ref,
        derived_uv_argv=domain_digest(
            DigestDomain.DERIVED_UV_ARGV,
            f"{label}:uv-argv".encode(),
        ),
        instance_content_set=instance_content_set,
    )
    marker_raw = canonical_json_bytes(marker.model_dump(mode="json"))
    marker_ref = record_ref(
        DigestDomain.ENVIRONMENT_MARKER,
        marker_raw,
        schema_version=marker.schema_version,
    )
    statement = authority_module.evidence_module.DependencyProfileEnvironmentStatement(
        schema_version="polisyos.foundry.dependency-environment.v1",
        admission_ref=admission_ref
        or record_ref(
            DigestDomain.PROFILE_ADMISSION,
            canonical_json_bytes(profile.admission.model_dump(mode="json")),
            schema_version=profile.admission.schema_version,
        ),
        stable_closure=profile.stable_closure,
        appointment_ref=_c1_ref(
            DigestDomain.PRODUCTION_APPOINTMENT,
            f"{label}:appointment",
        ),
        sync_root_access_ref=sync_root_access_ref
        or _c1_ref(DigestDomain.ROOT_ACCESS, f"{label}:root-access"),
        sync_root_access_binding_ref=sync_root_access_binding_ref
        or _c1_ref(
            DigestDomain.SIGNED_RECORD_BINDING,
            f"{label}:root-access-binding",
        ),
        python_runtime_installation_ref=runtime_installation_ref,
        python_runtime_verification_ref=runtime_verification_ref,
        observed_distributions=tuple(observed) + extra_distributions,
        stable_content_set=profile.stable_content_set,
        instance_content_set=instance_content_set,
        marker_ref=marker_ref,
    )
    receipt = DependencyProfileEnvironmentReceipt(
        receipt_ref=record_ref(
            DigestDomain.ENVIRONMENT_RECEIPT,
            canonical_json_bytes(statement.model_dump(mode="json")),
            schema_version=statement.schema_version,
        ),
        statement=statement,
        predicate_class="recomputed",
    )
    root = tmp_path / label
    if write_marker:
        marker_path = root / ".polisyos-foundry-authority-v1" / "environment-marker.json"
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_bytes(marker_raw)
    return _CandidateEnvironmentFixture(
        root=root,
        marker=marker,
        marker_raw=marker_raw,
        receipt=receipt,
        evidence=_ExactEnvironmentEvidence({marker_ref.artifact_id: marker_raw}),
    )


def _assert_current_cutoff_refusal(
    result: UnestablishedMethodCatalogDependencyProfile,
) -> None:
    assert result.result_kind is NegativeDependencyAuthorityResultKind.RUNTIME_CUTOFF_NOT_ESTABLISHED
    assert result.status == "not_established"
    refusal = result.preflight_refusal
    assert refusal.failure.predicate_id is AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF
    assert (
        refusal.failure.failure_code
        is AuthorityFailureCode.RUNTIME_SUBTREE_CUTOFF_NOT_ESTABLISHED
    )
    assert refusal.failure.missing_capability == "owner_enforced_runtime_subtree_cutoff"
    assert refusal.failure.missing_capability_state == "absent/unallocated"
    assert refusal.failure.candidate_runtime_evidence.status == "not_requested"
    assert refusal.persistence.status == "not_established"
    assert (
        refusal.persistence.missing_capability
        == "owner_resolved_resolution_receipt_store"
    )
    assert refusal.persistence.missing_capability_state == "absent/unallocated"


def test_current_production_authority_returns_only_unpersisted_cutoff_refusal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )

    assert isinstance(result, UnestablishedMethodCatalogDependencyProfile)
    _assert_current_cutoff_refusal(result)


def test_source_failure_and_cutoff_refusal_precede_repository_sync_and_candidate_edges(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    def forbidden_edge(*_args: object, **_kwargs: object) -> None:
        pytest.fail("production authority crossed the runtime-cutoff refusal")

    for name in (
        "_open_production_dependency_authority_repository",
        "_resolve_owner_components_for_request",
        "resolve_dependency_profile",
        "reconcile_bound_installed_environment",
    ):
        monkeypatch.setattr(authority_module, name, forbidden_edge)

    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )

    assert isinstance(result, UnestablishedMethodCatalogDependencyProfile)
    _assert_current_cutoff_refusal(result)


def test_source_mismatch_is_rejected_before_runtime_cutoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root, _product_root, previous = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    marker = repo_root / "unrelated.txt"
    marker.write_text("moves the observed tree\n", encoding="utf-8")
    _git_at(repo_root, "add", "--", marker.name)
    _git_at(repo_root, "commit", "-m", "move observed source")
    request = _authority_request(tmp_path, source_freeze=previous)

    result = build_production_method_catalog_dependency_authority().resolve(request)

    assert result.result_kind is NegativeDependencyAuthorityResultKind.SOURCE_REJECTED
    assert result.status == "rejected"
    assert result.failure.predicate_id is AuthorityPredicateId.SOURCE_FREEZE
    assert result.failure.failure_code is AuthorityFailureCode.SOURCE_FREEZE_MISMATCH
    assert result.persistence.status == "not_established"


def test_dirty_authority_source_is_not_established(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    profile_registry = (
        product_root
        / "architecture"
        / "production_quality"
        / "method_catalog_dependency_profiles.toml"
    )
    profile_registry.write_text(
        profile_registry.read_text(encoding="utf-8") + "\n# uncommitted\n",
        encoding="utf-8",
    )

    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )

    assert result.result_kind is NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED
    assert result.status == "not_established"
    assert result.failure.failure_code is AuthorityFailureCode.SOURCE_NOT_ESTABLISHED


@pytest.mark.parametrize("raw", ["relative", "../escape", "", "."])
def test_authority_request_rejects_non_absolute_roots(raw: str) -> None:
    with pytest.raises(ValueError, match="absolute"):
        MethodCatalogDependencyAuthorityRequest(
            authority_purpose="n8_method_catalog_reconstruction",
            expected_source_freeze_commit="0" * 40,
            production_data_root=AbsoluteRequestPath(value=Path(raw)),
            environment_root=AbsoluteRequestPath(value=Path("/tmp/environment")),
        )


@pytest.mark.parametrize("cause", ["missing", "unreadable"])
def test_missing_and_unreadable_manifest_share_public_typed_cause(
    cause: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    declaration = load_dependency_profile_registry(_PROFILE_REGISTRY).declarations[0]
    production_root = tmp_path / "production_data"
    production_root.mkdir()
    manifest_path = production_root / "manifest.json"
    if cause == "unreadable":
        manifest_path.write_bytes(b"{}")
        original_read_bytes = Path.read_bytes

        def unreadable_manifest(candidate: Path) -> bytes:
            if candidate == manifest_path:
                raise PermissionError("appointed manifest is unreadable")
            return original_read_bytes(candidate)

        monkeypatch.setattr(Path, "read_bytes", unreadable_manifest)

    manifest_input = read_candidate_production_data_manifest(production_root)

    result = resolve_dependency_profile(
        declaration,
        pyproject_bytes=b"not consulted",
        lockfile_bytes=b"not consulted",
        marker_environment={},
        production_data_manifest=manifest_input,
        admission=_admission(declaration),
    )

    assert isinstance(result, ProductionDataManifestMissingFailure)
    assert result.kind == "production_data_manifest_missing"
    assert result.code is AuthorityFailureCode.MANIFEST_MISSING
    assert result.predicate_id is AuthorityPredicateId.PRODUCTION_MANIFEST
    assert result.predicate_class == "not_established"
    assert result.cause == cause


def test_novel_profile_resolves_from_toml_without_code_change(tmp_path: Path) -> None:
    pyproject_ref = domain_digest(
        DigestDomain.PYPROJECT,
        (_PRODUCT_ROOT / "pyproject.toml").read_bytes(),
    )
    lockfile_ref = domain_digest(
        DigestDomain.UV_LOCK,
        (_PRODUCT_ROOT / "uv.lock").read_bytes(),
    )
    novel_registry = tmp_path / "profiles.toml"
    novel_registry.write_text(
        _PROFILE_REGISTRY.read_text(encoding="utf-8")
        + "\n[[declarations]]\n"
        + 'schema_version = "polisyos.foundry.dependency-profile.v1"\n'
        + 'profile_id = "zz-novel-n8-profile"\n'
        + 'root_distribution = "policy-engine"\n'
        + 'extras = ["analytics", "bayesian", "ml", "optimization-advanced", "solvers"]\n'
        + 'python_constraint = ">=3.14,<3.15"\n'
        + 'resolver_name = "uv"\n'
        + 'resolver_version = "0.9.21"\n'
        + f'pyproject_sha256 = "{pyproject_ref.value}"\n'
        + f'uv_lock_sha256 = "{lockfile_ref.value}"\n',
        encoding="utf-8",
    )

    registry = load_dependency_profile_registry(novel_registry)
    declaration = resolve_profile_declaration(registry, profile_id="zz-novel-n8-profile")
    result = resolve_dependency_profile(
        declaration,
        pyproject_bytes=(_PRODUCT_ROOT / "pyproject.toml").read_bytes(),
        lockfile_bytes=(_PRODUCT_ROOT / "uv.lock").read_bytes(),
        marker_environment=_marker_environment(),
        production_data_manifest=ProductionDataManifestPresent(
            kind="present",
            exact_bytes=b"{}",
        ),
        admission=_admission(declaration),
    )

    assert isinstance(result, ResolvedMethodCatalogDependencyProfile)
    assert result.declaration.profile_id == "zz-novel-n8-profile"
    assert result.distributions


def test_cross_object_admission_or_reconciliation_mismatch_is_schema_invalid() -> None:
    declaration = load_dependency_profile_registry(_PROFILE_REGISTRY).declarations[0]
    mismatched_admission = MethodCatalogProfileAdmission(
        schema_version="polisyos.foundry.profile-admission.v1",
        authority_purpose="n8_method_catalog_reconstruction",
        profile_id=declaration.profile_id,
        declaration_ref=record_ref(
            DigestDomain.PROFILE_DECLARATION,
            b"different-declaration",
            schema_version=declaration.schema_version,
        ),
        python_runtime_ref=record_ref(
            DigestDomain.TOOLCHAIN_RUNTIME,
            b"candidate-python-runtime",
            schema_version="polisyos.foundry.python-runtime-manifest.v1",
        ),
        uv_executable_ref=record_ref(
            DigestDomain.TOOLCHAIN_EXECUTABLE,
            b"candidate-uv-executable",
            schema_version="polisyos.foundry.executable-blob.v1",
        ),
        production_data_trust_policy_ref=record_ref(
            DigestDomain.TRUST_POLICY,
            b"candidate-production-data-trust-policy",
            schema_version="polisyos.foundry.production-data-trust-policy.v1",
        ),
        predicate_class="recomputed",
    )

    result = resolve_dependency_profile(
        declaration,
        pyproject_bytes=(_PRODUCT_ROOT / "pyproject.toml").read_bytes(),
        lockfile_bytes=(_PRODUCT_ROOT / "uv.lock").read_bytes(),
        marker_environment=_marker_environment(),
        production_data_manifest=ProductionDataManifestPresent(
            kind="present",
            exact_bytes=b"{}",
        ),
        admission=mismatched_admission,
    )

    assert isinstance(result, DigestPredicateMismatch)
    assert result.predicate_id is AuthorityPredicateId.PURPOSE_PROFILE
    assert result.code is AuthorityFailureCode.PROFILE_MISMATCH
    assert result.expected.domain is result.observed.domain is DigestDomain.PROFILE_DECLARATION
    assert result.expected.value != result.observed.value


def test_in_closure_substitution_changes_discriminant_without_name_rule() -> None:
    base = _resolve_tracked_profile()
    target = base.distributions[0]
    lock_bytes = (_PRODUCT_ROOT / "uv.lock").read_bytes()
    needle = f'name = "{target.name}"\nversion = "{target.version}"'.encode()
    replacement = f'name = "{target.name}"\nversion = "9999.0"'.encode()
    assert lock_bytes.count(needle) == 1
    mutated_lock = lock_bytes.replace(needle, replacement, 1)
    original = base.declaration
    declaration = MethodCatalogDependencyProfileDeclaration(
        schema_version=original.schema_version,
        profile_id=original.profile_id,
        root_distribution=original.root_distribution,
        extras=original.extras,
        python_constraint=original.python_constraint,
        resolver_name=original.resolver_name,
        resolver_version=original.resolver_version,
        pyproject_ref=original.pyproject_ref,
        lockfile_ref=DomainDigest(
            domain=DigestDomain.UV_LOCK,
            value=domain_digest(DigestDomain.UV_LOCK, mutated_lock).value,
        ),
    )

    changed = resolve_dependency_profile(
        declaration,
        pyproject_bytes=(_PRODUCT_ROOT / "pyproject.toml").read_bytes(),
        lockfile_bytes=mutated_lock,
        marker_environment=_marker_environment(),
        production_data_manifest=ProductionDataManifestPresent(
            kind="present",
            exact_bytes=b"{}",
        ),
        admission=_admission(declaration),
    )

    assert isinstance(changed, ResolvedMethodCatalogDependencyProfile)
    assert changed.stable_closure != base.stable_closure


def test_research_receipt_cannot_relabel_itself_as_n8_profile(
    tmp_path: Path,
) -> None:
    profile = _resolve_tracked_profile()
    first = profile.distributions[0]
    forged_selection = domain_digest(
        DigestDomain.SELECTED_DISTRIBUTION,
        b"torch==2.10.0-research-selection",
    )
    fixture = _candidate_environment_fixture(
        tmp_path,
        profile,
        label="research-relabel",
        selected_overrides={first.name: ("2.10.0", forged_selection)},
        admission_ref=_c1_ref(
            DigestDomain.PROFILE_ADMISSION,
            "research-profile-admission",
        ),
    )

    result = reconcile_bound_installed_environment(
        profile,
        environment_root=fixture.root,
        environment_receipt=fixture.receipt,
        evidence=fixture.evidence,
    )

    assert result.status == "fail"
    assert {failure.code for failure in result.failures} == {
        AuthorityFailureCode.PROFILE_MISMATCH,
        AuthorityFailureCode.CONTENT_MISMATCH,
    }
    assert all(
        failure.expected != failure.observed
        for failure in result.failures
        if isinstance(failure, DigestPredicateMismatch)
    )


def test_out_of_closure_distribution_is_non_decisive(tmp_path: Path) -> None:
    profile = _resolve_tracked_profile()
    extra = authority_module.evidence_module.InstalledDistributionIdentity(
        normalized_name="unrelated-observation",
        version="1.0",
        selected_artifact_ref=record_ref(
            DigestDomain.SELECTED_DISTRIBUTION,
            b"unrelated-observation",
            schema_version="polisyos.foundry.selected-distribution.v1",
        ),
        observed_stable_manifest_ref=_c1_ref(
            DigestDomain.INSTALLED_STABLE,
            "unrelated-stable",
        ),
        observed_instance_manifest_ref=_c1_ref(
            DigestDomain.INSTALLED_INSTANCE,
            "unrelated-instance",
        ),
        observed_source_binding_ref=_c1_ref(
            DigestDomain.INSTALLED_BINDING,
            "unrelated-binding",
        ),
    )
    base = _candidate_environment_fixture(
        tmp_path,
        profile,
        label="base-instance",
    )
    with_extra = _candidate_environment_fixture(
        tmp_path,
        profile,
        label="extra-instance",
        extra_distributions=(extra,),
    )

    base_result = reconcile_bound_installed_environment(
        profile,
        environment_root=base.root,
        environment_receipt=base.receipt,
        evidence=base.evidence,
    )
    extra_result = reconcile_bound_installed_environment(
        profile,
        environment_root=with_extra.root,
        environment_receipt=with_extra.receipt,
        evidence=with_extra.evidence,
    )

    assert base_result.status == extra_result.status == "pass"
    assert (
        base_result.predicate_class
        == extra_result.predicate_class
        == "independently_reconciled"
    )
    assert base_result.stable_closure == extra_result.stable_closure
    assert base_result.environment_receipt_ref != extra_result.environment_receipt_ref


def test_receipt_copy_without_target_marker_fails(tmp_path: Path) -> None:
    profile = _resolve_tracked_profile()
    source = _candidate_environment_fixture(
        tmp_path,
        profile,
        label="source-environment",
    )
    copied_receipt = DependencyProfileEnvironmentReceipt.model_validate_json(
        source.receipt.model_dump_json()
    )
    target_root = tmp_path / "copied-receipt-target"
    target_root.mkdir()

    result = reconcile_bound_installed_environment(
        profile,
        environment_root=target_root,
        environment_receipt=copied_receipt,
        evidence=source.evidence,
    )

    assert result.status == "fail"
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.predicate_id is AuthorityPredicateId.ENVIRONMENT_RECEIPT
    assert failure.code is AuthorityFailureCode.ENVIRONMENT_NOT_ESTABLISHED
    assert failure.predicate_class == "not_established"


def test_untraversed_marker_input_is_non_decisive() -> None:
    base = _resolve_tracked_profile()
    declaration = base.declaration
    marker_environment = _marker_environment()
    marker_environment["candidate_only_noise"] = "different"

    observed = resolve_dependency_profile(
        declaration,
        pyproject_bytes=(_PRODUCT_ROOT / "pyproject.toml").read_bytes(),
        lockfile_bytes=(_PRODUCT_ROOT / "uv.lock").read_bytes(),
        marker_environment=marker_environment,
        production_data_manifest=ProductionDataManifestPresent(
            kind="present",
            exact_bytes=b"{}",
        ),
        admission=_admission(declaration),
    )

    assert isinstance(observed, ResolvedMethodCatalogDependencyProfile)
    assert observed.marker_environment == base.marker_environment
    assert observed.stable_closure == base.stable_closure


def test_domain_digest_frames_domain_length_and_preimage() -> None:
    raw = b"same payload"
    prefix = b"polisyos.foundry.raw-blob.v1\0"
    expected = "sha256:" + hashlib.sha256(
        prefix + len(raw).to_bytes(8, "big") + raw
    ).hexdigest()

    assert domain_digest(DigestDomain.RAW_BLOB, raw).value == expected


@pytest.mark.parametrize(
    "raw",
    ("", ".", "/absolute", "../escape", "nested/../escape", "a//b", "nul\x00x"),
)
def test_runtime_paths_reject_empty_dot_absolute_dotdot_noncanonical_and_nul_variants(
    raw: str,
) -> None:
    with pytest.raises(ValueError):
        RootedRelativePath(value=raw)


def test_owner_capability_rejects_empty_object_new_mutated_token_and_wrong_family() -> None:
    @dataclass(frozen=True, slots=True)
    class Payload:
        value: str

    token_types = tuple(
        authority_module._fieldless_owner_token(type(f"Token{index}", (), {}))
        for index, _kind in enumerate(authority_module.OwnerCapabilityKind)
    )
    specs = tuple(
        authority_module._OwnerPayloadSpec(
            kind=kind,
            token_type=token_type,
            payload_type=Payload,
            exact_concrete_leaves=(),
            dynamic_record_domain_path=None,
            dynamic_record_ref_domain_path=None,
            child_resource_paths=(),
            nested_tokens=(),
        )
        for kind, token_type in zip(
            authority_module.OwnerCapabilityKind,
            token_types,
            strict=True,
        )
    )
    lock = RLock()
    fork_participants: list[object] = []

    @contextmanager
    def lifecycle() -> object:
        with lock:
            yield

    def claim(**_kwargs: object) -> authority_module._OwnerResourceClaim:
        return authority_module._OwnerResourceClaim(lease=object(), resources=())

    mint, unwrap, release = authority_module._build_owner_capability_kernel(
        specs,
        claim_owner_resources=claim,
        release_owner_resources=lambda _claim: None,
        register_fork_participant=fork_participants.append,
        lifecycle_section=lifecycle,
    )
    token = mint(specs[0], Payload(value="bound"))
    with unwrap(token, specs[0]) as payload:
        assert payload == Payload(value="bound")
    with (
        pytest.raises(
            authority_module.OwnerCapabilityFault,
            match="wrong_token_type",
        ),
        unwrap(object(), specs[0]),
    ):
        pass
    with (
        pytest.raises(
            authority_module.OwnerCapabilityFault,
            match="wrong_token_type",
        ),
        unwrap(token, specs[1]),
    ):
        pass
    release(token, specs[0])
    release(token, specs[0])
    assert len(fork_participants) == 1


def test_owner_payload_protocol_lookalike_wrong_domain_or_nested_token_rejects_before_mint() -> None:
    specs, mint, _unwrap, _release, _participants = _build_synthetic_owner_kernel()

    @dataclass(frozen=True, slots=True)
    class ProtocolLookalike:
        value: str

    with pytest.raises(
        authority_module.OwnerCapabilityFault,
        match="wrong_capability_family",
    ):
        mint(specs[0], ProtocolLookalike(value="same shape"))  # type: ignore[operator]

    wrong_domain = replace(
        specs[0],
        dynamic_record_domain_path=("value",),
        dynamic_record_ref_domain_path=("value",),
    )
    with pytest.raises(TypeError, match="domain"):
        _construct_owner_kernel((wrong_domain, *specs[1:]))

    wrong_nested = replace(
        specs[0],
        nested_tokens=(
            authority_module._OwnerNestedTokenSpec(
                payload_path=("value",),
                cardinality=authority_module._OwnerNestedCardinality.SINGLE,
                token_path=(),
                expected_domain_path=None,
                nested_kind=authority_module.OwnerCapabilityKind.RUNTIME_INSTALLATION,
            ),
        ),
    )
    with pytest.raises(TypeError, match="nested"):
        _construct_owner_kernel((wrong_nested, *specs[1:]))


def test_raw_string_kind_undecorated_token_and_list_spec_fail_before_mapping_access() -> None:
    specs, _mint, _unwrap, _release, _participants = _build_synthetic_owner_kernel()
    raw_kind = replace(specs[0], kind="canonical-source")  # type: ignore[arg-type]
    undecorated = replace(specs[0], token_type=type("Undecorated", (), {}))
    for mutated in ((raw_kind, *specs[1:]), (undecorated, *specs[1:])):
        with pytest.raises(TypeError):
            _construct_owner_kernel(mutated)
    with pytest.raises(TypeError, match="exactly cover"):
        _construct_owner_kernel(list(specs))  # type: ignore[arg-type]


def test_copying_token_marker_onto_stateful_class_fails_behavioral_token_check() -> None:
    class Stateful:
        pass

    Stateful.__owner_token_class_marker__ = authority_module._OWNER_TOKEN_CLASS_MARKER
    with pytest.raises(TypeError, match="fieldless/frozen/identity-only"):
        authority_module._validate_fieldless_owner_token_type(Stateful)


def test_token_with_inherited_writable_slot_fails_object_only_mro_check() -> None:
    class WritableBase:
        __slots__ = ("state",)

    class InheritedToken(WritableBase):
        __slots__ = ("__weakref__",)

    InheritedToken.__owner_token_class_marker__ = (
        authority_module._OWNER_TOKEN_CLASS_MARKER
    )
    with pytest.raises(TypeError, match="fieldless/frozen/identity-only"):
        authority_module._validate_fieldless_owner_token_type(InheritedToken)


def test_unhashable_metaclass_in_rogue_spec_fails_before_token_map_access() -> None:
    class UnhashableType(type):
        __hash__ = None  # type: ignore[assignment]

    class RogueToken(metaclass=UnhashableType):
        pass

    RogueToken.__owner_token_class_marker__ = authority_module._OWNER_TOKEN_CLASS_MARKER
    specs, _mint, _unwrap, _release, _participants = _build_synthetic_owner_kernel()
    rogue = replace(specs[0], token_type=RogueToken)
    with pytest.raises(TypeError, match="fieldless/frozen/identity-only"):
        _construct_owner_kernel((rogue, *specs[1:]))


def test_nonexistent_or_wrong_typed_leaf_nested_and_domain_paths_fail_construction() -> None:
    specs, _mint, _unwrap, _release, _participants = _build_synthetic_owner_kernel()
    mutations = (
        replace(
            specs[0],
            exact_concrete_leaves=(
                authority_module._OwnerPayloadLeafSpec(("absent",), str),
            ),
        ),
        replace(
            specs[0],
            exact_concrete_leaves=(
                authority_module._OwnerPayloadLeafSpec(("value",), int),
            ),
        ),
        replace(
            specs[0],
            dynamic_record_domain_path=("value",),
            dynamic_record_ref_domain_path=("absent",),
        ),
    )
    for mutation in mutations:
        with pytest.raises(TypeError):
            _construct_owner_kernel((mutation, *specs[1:]))


def test_rogue_twelfth_token_or_duplicate_capability_kind_fails_bijection() -> None:
    specs, _mint, _unwrap, _release, _participants = _build_synthetic_owner_kernel()
    with pytest.raises(TypeError, match="exactly cover"):
        _construct_owner_kernel((*specs, specs[0]))
    duplicate_kind = replace(specs[-1], kind=specs[0].kind)
    with pytest.raises(TypeError, match="bijection"):
        _construct_owner_kernel((*specs[:-1], duplicate_kind))


def test_owner_kernel_exposes_no_live_entry_or_payload_registry() -> None:
    specs, mint, unwrap, release, _participants = _build_synthetic_owner_kernel()
    token = mint(specs[0], _SyntheticOwnerPayload(value="sealed"))  # type: ignore[operator]
    assert not hasattr(token, "__dict__")
    assert vars(type(token)).get("payload") is None
    assert not {
        "instances",
        "spec_by_kind",
        "spec_by_token",
        "owner_payload_registry",
    }.intersection(vars(authority_module))
    with unwrap(token, specs[0]) as payload:  # type: ignore[operator]
        assert payload == _SyntheticOwnerPayload(value="sealed")
    release(token, specs[0])  # type: ignore[operator]


def test_every_registered_child_resource_is_weakrefable_before_open() -> None:
    resource_types = {
        leaf.exact_concrete_type
        for spec in authority_module._OWNER_CAPABILITY_SPECS
        for leaf in spec.exact_concrete_leaves
        if leaf.field_path in spec.child_resource_paths
    }
    assert resource_types == {
        authority_module._PosixOpenedDirectoryHandle,
        authority_module._InstitutionalRootHandle,
    }
    for resource_type in resource_types:
        instance = object.__new__(resource_type)
        assert weakref.ref(instance)() is instance


def test_wrong_payload_or_fake_child_fails_before_any_coordinator_or_child_call() -> None:
    calls = 0

    def on_claim(_resources: object) -> None:
        nonlocal calls
        calls += 1

    specs, mint, _unwrap, _release, _leases = _build_resource_backed_owner_kernel(
        on_claim=on_claim
    )
    with pytest.raises(authority_module.OwnerCapabilityFault):
        mint(specs[0], _SyntheticOwnerPayload(value="wrong payload"))  # type: ignore[operator]
    with pytest.raises(authority_module.OwnerCapabilityFault):
        mint(specs[0], _SyntheticResourcePayload(resource=object()))  # type: ignore[arg-type,operator]
    assert calls == 0


def test_wrong_signed_record_lookalike_property_is_never_accessed_before_type_fault() -> None:
    class HostileLookalike:
        @property
        def record_domain(self) -> object:
            raise AssertionError("hostile lookalike property was accessed")

    with pytest.raises(
        authority_module.OwnerCapabilityFault,
        match="wrong_capability_family",
    ):
        authority_module._mint_owner_capability(
            authority_module._SIGNED_RECORD_SPEC,
            HostileLookalike(),
        )


def test_failed_mint_rolls_back_and_closes_every_provisional_resource() -> None:
    payload: _SyntheticResourcePayload

    def corrupt_after_claim(_resources: object) -> None:
        payload.resource = object()  # type: ignore[assignment]

    specs, mint, _unwrap, _release, leases = _build_resource_backed_owner_kernel(
        on_claim=corrupt_after_claim
    )
    resource = _SyntheticOwnerResource(key=1)
    payload = _SyntheticResourcePayload(resource=resource)
    with pytest.raises(authority_module.OwnerCapabilityFault):
        mint(specs[0], payload)  # type: ignore[operator]
    assert resource.closed
    assert leases == {}


def test_corrupt_sibling_after_valid_open_handle_closes_generation_on_mint_failure() -> None:
    payload: _SyntheticResourcePayload

    def replace_registered_child(_resources: object) -> None:
        payload.resource = _SyntheticOwnerResource(key=2)

    specs, mint, _unwrap, _release, leases = _build_resource_backed_owner_kernel(
        on_claim=replace_registered_child
    )
    originally_claimed = _SyntheticOwnerResource(key=1)
    payload = _SyntheticResourcePayload(resource=originally_claimed)
    with pytest.raises(authority_module.OwnerCapabilityFault):
        mint(specs[0], payload)  # type: ignore[operator]
    assert originally_claimed.closed
    assert leases == {}


def _isolated_owner_resource_coordinator() -> tuple[object, ...]:
    return authority_module._build_owner_resource_coordinator(
        specs=authority_module.cast(
            "tuple[authority_module._OwnerPayloadSpec[object, object], ...]",
            authority_module._OWNER_CAPABILITY_SPECS,
        )
    )


def test_claim_internal_failure_leaves_no_partial_lease_or_open_provisional() -> None:
    coordinator = _isolated_owner_resource_coordinator()
    claim = coordinator[4]
    release = coordinator[5]
    first = _SyntheticOwnerResource(key=1)
    failing = _SyntheticOwnerResource(key=2, fail_key=True)
    with pytest.raises(OSError, match="lease-key failure"):
        claim(  # type: ignore[operator]
            capability_kind=authority_module.OwnerCapabilityKind.CANONICAL_SOURCE,
            resources=(first, failing),
        )
    admitted = claim(  # type: ignore[operator]
        capability_kind=authority_module.OwnerCapabilityKind.CANONICAL_SOURCE,
        resources=(first,),
    )
    release(admitted)  # type: ignore[operator]
    assert first.closed


def test_concurrent_same_generation_mint_admits_exactly_one_resource_lease() -> None:
    coordinator = _isolated_owner_resource_coordinator()
    claim = coordinator[4]
    release = coordinator[5]
    resource = _SyntheticOwnerResource(key=7)
    barrier = Barrier(3)
    outcomes: list[object] = []

    def contender() -> None:
        barrier.wait()
        try:
            outcomes.append(
                claim(  # type: ignore[operator]
                    capability_kind=authority_module.OwnerCapabilityKind.CANONICAL_SOURCE,
                    resources=(resource,),
                )
            )
        except authority_module.OwnerCapabilityFault as error:
            outcomes.append(error)

    threads = (Thread(target=contender), Thread(target=contender))
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    claims = tuple(
        row for row in outcomes if isinstance(row, authority_module._OwnerResourceClaim)
    )
    faults = tuple(
        row for row in outcomes if isinstance(row, authority_module.OwnerCapabilityFault)
    )
    assert len(claims) == len(faults) == 1
    assert faults[0].code is authority_module.OwnerCapabilityFaultCode.RESOURCE_ALREADY_OWNED
    release(claims[0])  # type: ignore[operator]


def test_release_and_token_tombstone_are_atomic_against_payload_borrow() -> None:
    specs, mint, unwrap, release, _participants = _build_synthetic_owner_kernel()
    token = mint(specs[0], _SyntheticOwnerPayload(value="borrowed"))  # type: ignore[operator]
    with (
        unwrap(token, specs[0]),  # type: ignore[operator]
        pytest.raises(
            authority_module.OwnerCapabilityFault,
            match="resource_in_use",
        ),
    ):
        release(token, specs[0])  # type: ignore[operator]
    release(token, specs[0])  # type: ignore[operator]
    with (
        pytest.raises(authority_module.OwnerCapabilityFault, match="unminted_token"),
        unwrap(token, specs[0]),  # type: ignore[operator]
    ):
        pass


def test_inherited_live_token_is_forked_not_unminted_but_forgery_is_unminted() -> None:
    specs, mint, unwrap, _release, participants = _build_synthetic_owner_kernel()
    token = mint(specs[0], _SyntheticOwnerPayload(value="parent"))  # type: ignore[operator]
    participants[0](True)  # type: ignore[operator]
    with (
        pytest.raises(authority_module.OwnerCapabilityFault, match="forked_process"),
        unwrap(token, specs[0]),  # type: ignore[operator]
    ):
        pass
    forged = object.__new__(specs[0].token_type)
    with (
        pytest.raises(authority_module.OwnerCapabilityFault, match="unminted_token"),
        unwrap(forged, specs[0]),  # type: ignore[operator]
    ):
        pass


def test_drop_and_collect_token_closes_descriptor_before_later_fork() -> None:
    specs, mint, _unwrap, _release, leases = _build_resource_backed_owner_kernel()
    resource = _SyntheticOwnerResource(key=11)
    token = mint(specs[0], _SyntheticResourcePayload(resource=resource))  # type: ignore[operator]
    token_ref = weakref.ref(token)
    del token
    gc.collect()
    assert token_ref() is None
    assert resource.closed
    assert leases == {}


def test_two_tokens_cannot_share_one_resource_handle() -> None:
    specs, mint, _unwrap, release, _leases = _build_resource_backed_owner_kernel()
    resource = _SyntheticOwnerResource(key=12)
    first = mint(specs[0], _SyntheticResourcePayload(resource=resource))  # type: ignore[operator]
    try:
        with pytest.raises(
            authority_module.OwnerCapabilityFault,
            match="resource_already_owned",
        ):
            mint(specs[0], _SyntheticResourcePayload(resource=resource))  # type: ignore[operator]
    finally:
        release(first, specs[0])  # type: ignore[operator]


def test_explicit_release_closes_descriptor_and_invalidates_token_idempotently() -> None:
    specs, mint, unwrap, release, _leases = _build_resource_backed_owner_kernel()
    resource = _SyntheticOwnerResource(key=13)
    token = mint(specs[0], _SyntheticResourcePayload(resource=resource))  # type: ignore[operator]
    release(token, specs[0])  # type: ignore[operator]
    release(token, specs[0])  # type: ignore[operator]
    assert resource.closed
    with (
        pytest.raises(authority_module.OwnerCapabilityFault, match="unminted_token"),
        unwrap(token, specs[0]),  # type: ignore[operator]
    ):
        pass


def test_disposal_failure_poison_rejects_fresh_mint_without_registering_token() -> None:
    specs, mint, _unwrap, release, _leases = _build_resource_backed_owner_kernel()
    resource = _SyntheticOwnerResource(key=14, fail_close=True)
    token = mint(specs[0], _SyntheticResourcePayload(resource=resource))  # type: ignore[operator]
    with pytest.raises(
        authority_module.OwnerCapabilityFault,
        match="child_resource_disposal_failed",
    ):
        release(token, specs[0])  # type: ignore[operator]
    with pytest.raises(
        authority_module.OwnerCapabilityFault,
        match="child_resource_disposal_failed",
    ):
        mint(specs[1], _SyntheticOwnerPayload(value="poisoned"))  # type: ignore[operator]


def test_drop_open_handle_before_mint_closes_generation_by_finalizer(
    tmp_path: Path,
) -> None:
    coordinator = _isolated_owner_resource_coordinator()
    open_directory, require_descriptor = coordinator[:2]
    root = tmp_path / "root"
    root.mkdir()
    handle = open_directory(  # type: ignore[operator]
        directory=root,
        owner_kind=authority_module.OwnerCapabilityKind.CANONICAL_SOURCE,
        handle_type=authority_module._PosixOpenedDirectoryHandle,
    )
    descriptor = require_descriptor(handle)  # type: ignore[operator]
    handle_ref = weakref.ref(handle)
    del handle
    gc.collect()
    assert handle_ref() is None
    with pytest.raises(OSError):
        os.fstat(descriptor)


def test_fork_after_descriptor_open_before_mint_closes_unclaimed_generation(
    tmp_path: Path,
) -> None:
    coordinator = _isolated_owner_resource_coordinator()
    open_directory, require_descriptor = coordinator[:2]
    before_fork, after_child = coordinator[8], coordinator[10]
    root = tmp_path / "root"
    root.mkdir()
    handle = open_directory(  # type: ignore[operator]
        directory=root,
        owner_kind=authority_module.OwnerCapabilityKind.CANONICAL_SOURCE,
        handle_type=authority_module._PosixOpenedDirectoryHandle,
    )
    before_fork()  # type: ignore[operator]
    after_child()  # type: ignore[operator]
    with pytest.raises(authority_module.OwnerCapabilityFault, match="forked_process"):
        require_descriptor(handle)  # type: ignore[operator]


def test_fork_closes_inherited_source_runtime_and_institutional_root_descriptors(
    tmp_path: Path,
) -> None:
    coordinator = _isolated_owner_resource_coordinator()
    open_directory, require_descriptor = coordinator[:2]
    before_fork, after_child = coordinator[8], coordinator[10]
    rows = (
        (
            authority_module.OwnerCapabilityKind.CANONICAL_SOURCE,
            authority_module._PosixOpenedDirectoryHandle,
        ),
        (
            authority_module.OwnerCapabilityKind.RUNTIME_INSTALLATION,
            authority_module._PosixOpenedDirectoryHandle,
        ),
        (
            authority_module.OwnerCapabilityKind.PRODUCTION_MOUNT,
            authority_module._InstitutionalRootHandle,
        ),
    )
    handles = []
    for index, (kind, handle_type) in enumerate(rows):
        root = tmp_path / f"root-{index}"
        root.mkdir()
        handles.append(
            open_directory(  # type: ignore[operator]
                directory=root,
                owner_kind=kind,
                handle_type=handle_type,
            )
        )
    before_fork()  # type: ignore[operator]
    after_child()  # type: ignore[operator]
    for handle in handles:
        with pytest.raises(
            authority_module.OwnerCapabilityFault,
            match="forked_process",
        ):
            require_descriptor(handle)  # type: ignore[operator]


def test_closed_wrapper_cannot_revive_after_fd_number_reuse(tmp_path: Path) -> None:
    coordinator = _isolated_owner_resource_coordinator()
    open_directory, require_descriptor, close_descriptor = coordinator[:3]
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first = open_directory(  # type: ignore[operator]
        directory=first_root,
        owner_kind=authority_module.OwnerCapabilityKind.CANONICAL_SOURCE,
        handle_type=authority_module._PosixOpenedDirectoryHandle,
    )
    first_fd = require_descriptor(first)  # type: ignore[operator]
    close_descriptor(first)  # type: ignore[operator]
    second = open_directory(  # type: ignore[operator]
        directory=second_root,
        owner_kind=authority_module.OwnerCapabilityKind.CANONICAL_SOURCE,
        handle_type=authority_module._PosixOpenedDirectoryHandle,
    )
    try:
        assert require_descriptor(second) >= 0  # type: ignore[operator]
        with pytest.raises(authority_module.OwnerCapabilityFault):
            require_descriptor(first)  # type: ignore[operator]
        assert first.descriptor == first_fd
    finally:
        close_descriptor(second)  # type: ignore[operator]


def test_raw_oserror_from_stale_descriptor_becomes_typed_not_established(
    tmp_path: Path,
) -> None:
    coordinator = _isolated_owner_resource_coordinator()
    open_directory, require_descriptor = coordinator[:2]
    root = tmp_path / "root"
    root.mkdir()
    handle = open_directory(  # type: ignore[operator]
        directory=root,
        owner_kind=authority_module.OwnerCapabilityKind.CANONICAL_SOURCE,
        handle_type=authority_module._PosixOpenedDirectoryHandle,
    )
    os.close(require_descriptor(handle))  # type: ignore[operator]
    with pytest.raises(authority_module.OwnerCapabilityFault) as captured:
        require_descriptor(handle)  # type: ignore[operator]
    assert captured.value.disposition is authority_module.OwnerCapabilityFaultDisposition.NOT_ESTABLISHED


def test_forked_handle_operation_rechecks_creator_process(tmp_path: Path) -> None:
    coordinator = _isolated_owner_resource_coordinator()
    open_directory, require_descriptor = coordinator[:2]
    root = tmp_path / "root"
    root.mkdir()
    handle = open_directory(  # type: ignore[operator]
        directory=root,
        owner_kind=authority_module.OwnerCapabilityKind.CANONICAL_SOURCE,
        handle_type=authority_module._PosixOpenedDirectoryHandle,
    )
    handle.creator_pid += 1
    with pytest.raises(authority_module.OwnerCapabilityFault, match="forked_process"):
        require_descriptor(handle)  # type: ignore[operator]


def test_disposal_failure_poison_rejects_fresh_open_without_registering_handle(
    tmp_path: Path,
) -> None:
    coordinator = _isolated_owner_resource_coordinator()
    open_directory, _require, _close, _key, claim, release = coordinator[:6]
    failing = _SyntheticOwnerResource(key=99, fail_close=True)
    owner_claim = claim(  # type: ignore[operator]
        capability_kind=authority_module.OwnerCapabilityKind.CANONICAL_SOURCE,
        resources=(failing,),
    )
    release(owner_claim)  # type: ignore[operator]
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(
        authority_module.OwnerCapabilityFault,
        match="child_resource_disposal_failed",
    ):
        open_directory(  # type: ignore[operator]
            directory=root,
            owner_kind=authority_module.OwnerCapabilityKind.CANONICAL_SOURCE,
            handle_type=authority_module._PosixOpenedDirectoryHandle,
        )


def _mint_test_signed_record(
    domain: DigestDomain,
    label: bytes,
) -> tuple[object, authority_module.FoundryRecordRef[DigestDomain]]:
    record = record_ref(
        domain,
        label,
        schema_version=f"polisyos.foundry.{domain.value}.v1",
    )
    statement = authority_module.SignedFoundryRecordBindingStatement[DigestDomain](
        schema_version="polisyos.foundry.signed-record-binding.v1",
        record_ref=record,
        signed_evidence_ref=record_ref(
            DigestDomain.SIGNED_EVIDENCE,
            label + b"-evidence",
            schema_version="polisyos.foundry.signed-artifact-evidence.v1",
        ),
        required_role=TrustRole.APPOINTMENT_ISSUER,
        verification_basis=authority_module.evidence_module.ResolvedTrustVerificationBasis(
            kind="resolved_trust",
            trust_resolution_receipt_ref=record_ref(
                DigestDomain.TRUST_RESOLUTION,
                label + b"-trust",
                schema_version="polisyos.foundry.trust-resolution.v1",
            ),
        ),
        verifier_provenance_ref=record_ref(
            DigestDomain.VERIFIER_PROVENANCE,
            label + b"-verifier",
            schema_version="polisyos.foundry.verifier-provenance.v1",
        ),
    )
    binding = authority_module.PersistedSignedFoundryRecordBinding[DigestDomain](
        binding_ref=record_ref(
            DigestDomain.SIGNED_RECORD_BINDING,
            canonical_json_bytes(statement.model_dump(mode="json")),
            schema_version=statement.schema_version,
        ),
        statement=statement,
    )
    payload = authority_module._VerifiedSignedFoundryRecordPayload(
        record_domain=domain,
        binding=binding,
        exact_record_bytes=label,
    )
    return (
        authority_module._mint_owner_capability(
            authority_module._SIGNED_RECORD_SPEC,
            payload,
        ),
        binding.binding_ref,
    )


def test_signed_record_token_rejects_a_different_expected_record_domain() -> None:
    token, _binding_ref = _mint_test_signed_record(
        DigestDomain.PRODUCTION_APPOINTMENT,
        b"appointment",
    )
    try:
        with (
            pytest.raises(
                authority_module.OwnerCapabilityFault,
                match="wrong_record_domain",
            ),
            authority_module._unwrap_owner_capability(
                token,
                authority_module._SIGNED_RECORD_SPEC,
                expected_record_domain=DigestDomain.PRODUCTION_CUSTODY,
            ),
        ):
            pass
    finally:
        authority_module._release_owner_capability(
            token,
            authority_module._SIGNED_RECORD_SPEC,
        )


def _mint_test_signed_graph(
    rows: tuple[
        tuple[DigestDomain, object, authority_module.FoundryRecordRef[DigestDomain]],
        ...,
    ],
) -> object:
    binding_refs = tuple(row[2] for row in rows)
    index_statement = authority_module.evidence_module.SignedRecordBindingIndexStatement(
        schema_version="polisyos.foundry.signed-binding-index.v1",
        source_authority_ref=record_ref(
            DigestDomain.CANONICAL_SOURCE,
            b"source",
            schema_version="polisyos.foundry.canonical-source-authority.v1",
        ),
        binding_refs=binding_refs,
    )
    payload = authority_module._VerifiedCapsuleSignedGraphPayload(
        index=authority_module.PersistedSignedRecordBindingIndex(
            index_ref=record_ref(
                DigestDomain.SIGNED_BINDING_INDEX,
                canonical_json_bytes(index_statement.model_dump(mode="json")),
                schema_version=index_statement.schema_version,
            ),
            statement=index_statement,
        ),
        verified_records=tuple(
            authority_module._VerifiedSignedGraphRecord(
                record_domain=domain,
                binding_ref=binding_ref,
                record=token,
            )
            for domain, token, binding_ref in rows
        ),
    )
    return authority_module._mint_owner_capability(
        authority_module._SIGNED_GRAPH_SPEC,
        payload,
    )


def test_signed_graph_recursively_binds_each_record_token_to_its_row_domain() -> None:
    appointment, appointment_binding = _mint_test_signed_record(
        DigestDomain.PRODUCTION_APPOINTMENT,
        b"appointment",
    )
    custody, custody_binding = _mint_test_signed_record(
        DigestDomain.PRODUCTION_CUSTODY,
        b"custody",
    )
    graph = _mint_test_signed_graph(
        (
            (DigestDomain.PRODUCTION_APPOINTMENT, appointment, appointment_binding),
            (DigestDomain.PRODUCTION_CUSTODY, custody, custody_binding),
        )
    )
    try:
        with authority_module._unwrap_owner_capability(
            graph,
            authority_module._SIGNED_GRAPH_SPEC,
        ) as payload:
            assert tuple(row.record_domain for row in payload.verified_records) == (
                DigestDomain.PRODUCTION_APPOINTMENT,
                DigestDomain.PRODUCTION_CUSTODY,
            )
    finally:
        authority_module._release_owner_capability(
            graph,
            authority_module._SIGNED_GRAPH_SPEC,
        )
        for token in (appointment, custody):
            authority_module._release_owner_capability(
                token,
                authority_module._SIGNED_RECORD_SPEC,
            )


def test_swapped_signed_graph_record_domain_fails_private_recursive_unwrap() -> None:
    appointment, appointment_binding = _mint_test_signed_record(
        DigestDomain.PRODUCTION_APPOINTMENT,
        b"appointment",
    )
    custody, custody_binding = _mint_test_signed_record(
        DigestDomain.PRODUCTION_CUSTODY,
        b"custody",
    )
    graph: object | None = None
    try:
        graph = _mint_test_signed_graph(
            (
                (DigestDomain.PRODUCTION_CUSTODY, appointment, appointment_binding),
                (DigestDomain.PRODUCTION_APPOINTMENT, custody, custody_binding),
            )
        )
        with (
            pytest.raises(
                authority_module.OwnerCapabilityFault,
                match="wrong_record_domain",
            ),
            authority_module._unwrap_owner_capability(
                graph,
                authority_module._SIGNED_GRAPH_SPEC,
            ),
        ):
            pass
    finally:
        if graph is not None:
            authority_module._release_owner_capability(
                graph,
                authority_module._SIGNED_GRAPH_SPEC,
            )
        for token in (appointment, custody):
            authority_module._release_owner_capability(
                token,
                authority_module._SIGNED_RECORD_SPEC,
            )


def test_trust_key_id_role_identity_and_revocation_are_recomputed() -> None:
    public_key = bytes(range(32))
    key_id = "sha256:" + hashlib.sha256(public_key).hexdigest()
    key = TrustPublicKey(
        key_id=key_id,
        algorithm="ed25519",
        public_key_encoding="raw-ed25519-32",
        public_key_bytes=public_key,
        signer_identity="foundry-test-root",
        roles=(TrustRole.FOUNDRY_TRUST_ROOT,),
    )
    revocation = TrustRevocationStatement(
        schema_version="polisyos.foundry.trust-revocation.v1",
        key_id=key.key_id,
        signer_identity=key.signer_identity,
        revoked_roles=key.roles,
        effective_source_freeze_commit="1" * 40,
    )

    assert revocation.key_id == key_id
    with pytest.raises(ValueError, match="recomputed"):
        TrustPublicKey(
            key_id="sha256:" + "0" * 64,
            algorithm="ed25519",
            public_key_encoding="raw-ed25519-32",
            public_key_bytes=public_key,
            signer_identity="foundry-test-root",
            roles=(TrustRole.FOUNDRY_TRUST_ROOT,),
        )


def test_duplicate_or_unsorted_trust_key_role_and_revocation_sets_reject_before_verifier() -> None:
    public_key = bytes(range(32))
    key_id = "sha256:" + hashlib.sha256(public_key).hexdigest()
    with pytest.raises(ValueError, match="canonically sorted"):
        TrustPublicKey(
            key_id=key_id,
            algorithm="ed25519",
            public_key_encoding="raw-ed25519-32",
            public_key_bytes=public_key,
            signer_identity="foundry-test-root",
            roles=(TrustRole.FOUNDRY_TRUST_ROOT, TrustRole.APPOINTMENT_ISSUER),
        )


@pytest.mark.parametrize(
    ("relation", "status"),
    (
        (GitCommitRelation.ANCESTOR, "effective"),
        (GitCommitRelation.EQUAL, "effective"),
        (GitCommitRelation.DESCENDANT, "future"),
        (GitCommitRelation.INCOMPARABLE, "not_established"),
    ),
)
def test_revocation_cutoff_uses_ancestor_equal_future_and_incomparable_git_relations(
    relation: GitCommitRelation,
    status: str,
) -> None:
    disposition = RevocationCutoffDisposition(
        revocation_ref=record_ref(
            DigestDomain.TRUST_REVOCATION,
            relation.value.encode(),
            schema_version="polisyos.foundry.trust-revocation.v1",
        ),
        relation_to_source_cutoff=relation,
        status=status,
    )
    assert disposition.status == status


def test_trust_policy_statement_has_no_self_reference() -> None:
    assert "trust_policy_ref" not in ProductionDataTrustPolicyStatement.model_fields


def test_digest_algebra_rejects_single_known_enum_member_substitution() -> None:
    registry = (
        _PRODUCT_ROOT
        / "architecture"
        / "production_quality"
        / "method_catalog_dependency_digest_domains.toml"
    ).read_bytes()
    mutated = registry.replace(
        b'producer_id = "raw_blob_v1"',
        b'producer_id = "canonical_statement_v1"',
        1,
    )
    assert mutated != registry

    with pytest.raises(ValueError, match="inseparable v1 variant"):
        decode_digest_domain_registry_toml(mutated)


def test_unknown_digest_producer_verifier_ordering_or_launcher_profile_fails_before_execution() -> None:
    registry = _DIGEST_REGISTRY.read_bytes()
    mutations = (
        registry.replace(
            b'producer_id = "raw_blob_v1"',
            b'producer_id = "future_raw_blob_v2"',
            1,
        ),
        registry.replace(
            b'verifier_id = "rehash_raw_blob_v1"',
            b'verifier_id = "trust_declared_digest_v1"',
            1,
        ),
        registry.replace(
            b'ordering_rule = "raw_bytes_identity"',
            b'ordering_rule = "ambient_iteration_order"',
            1,
        ),
    )
    for mutated in mutations:
        with pytest.raises(ValueError, match="unknown, aliased or non-exact"):
            decode_digest_domain_registry_toml(mutated)

    with pytest.raises(ValidationError):
        authority_module.LauncherProfileSpec.model_validate(
            {
                "profile_id": "future_launcher_v2",
                "supported_platform_family": ("darwin", "linux"),
                "python_abi": "cp314",
                "line_ending": "lf",
                "interpreter_occurrences": 1,
                "normalized_interpreter_token": "@PYTHON@",
                "expected_producer_id": "distlib_posix_console_v1",
                "observed_verifier_id": "parse_distlib_posix_console_v1",
            },
            strict=True,
        )


def test_digest_registry_toml_rejects_synthetic_enum_alias_whitespace_number_and_bool() -> None:
    registry = _DIGEST_REGISTRY.read_bytes()
    replacements = (
        b'domain_id = "raw_blob"',
        b'domain_id = " raw-blob"',
        b"domain_id = 1",
        b"domain_id = true",
    )
    for replacement in replacements:
        mutated = registry.replace(b'domain_id = "raw-blob"', replacement, 1)
        with pytest.raises(ValueError, match="exact string|unknown, aliased"):
            decode_digest_domain_registry_toml(mutated)


def test_digest_registry_toml_semantic_round_trip_reproduces_hash() -> None:
    raw = _DIGEST_REGISTRY.read_bytes()
    first = decode_digest_domain_registry_toml(raw)
    second = decode_digest_domain_registry_toml(raw + b"\n")

    assert first.statement == second.statement
    assert first.canonical_statement_bytes == second.canonical_statement_bytes
    assert first.semantic_hash == second.semantic_hash
    assert first.registry_ref.semantic_hash == second.registry_ref.semantic_hash
    assert first.registry_ref.artifact_id != second.registry_ref.artifact_id


def test_digest_prefix_hex_is_lowercase_nul_terminated_and_round_trips() -> None:
    registry = decode_digest_domain_registry_toml(_DIGEST_REGISTRY.read_bytes())
    for row in registry.statement.domains:
        assert row.prefix_hex == row.prefix_hex.lower()
        decoded = bytes.fromhex(row.prefix_hex)
        assert decoded.endswith(b"\0")
        assert decoded.hex() == row.prefix_hex
        assert decoded == f"polisyos.foundry.{row.domain_id.value}.v1\0".encode()


def test_sibling_owner_prefix_fails_exact_domain_derived_equality() -> None:
    registry = _DIGEST_REGISTRY.read_bytes()
    raw_prefix = next(
        line.split(b' = "', 1)[1][:-1]
        for line in registry.splitlines()
        if line.startswith(b"prefix_hex")
    )
    sibling_prefix = (
        b"polisyos.sibling.raw-blob.v1\0".hex().encode("ascii")
    )
    mutated = registry.replace(raw_prefix, sibling_prefix, 1)

    with pytest.raises(ValueError, match="domain-derived prefix"):
        decode_digest_domain_registry_toml(mutated)


def test_every_persisted_digest_domain_has_one_strict_statement_codec() -> None:
    registry = decode_digest_domain_registry_toml(_DIGEST_REGISTRY.read_bytes())
    observed = {
        kind: frozenset(
            row.domain_id
            for row in registry.statement.domains
            if row.algebra.preimage_kind is kind
        )
        for kind in DigestPreimageKind
    }

    assert observed == _EXPECTED_DOMAINS_BY_PREIMAGE_KIND
    assert sum(len(domains) for domains in observed.values()) == len(DigestDomain)
    for row in registry.statement.domains:
        assert row.derivation_rule
        assert row.derivation_evidence
    codecs = getattr(authority_module, "FOUNDRY_STATEMENT_CODECS", {})
    assert frozenset(codecs) == observed[DigestPreimageKind.CANONICAL_STATEMENT]
    handlers = authority_module.build_digest_domain_handlers(registry)
    assert frozenset(handlers) == frozenset(DigestDomain)
    for row in registry.statement.domains:
        handler = handlers[row.domain_id]
        assert handler.preimage_kind is row.algebra.preimage_kind
        assert handler.producer_id is row.algebra.producer_id
        assert handler.verifier_id is row.algebra.verifier_id

    request = authority_module.DependencyAuthorityPreSourceRequestStatement(
        schema_version="polisyos.foundry.dependency-pre-source-request.v1",
        authority_purpose="n8_method_catalog_reconstruction",
        expected_source_freeze_commit="1" * 40,
        production_data_request_token=domain_digest(
            DigestDomain.ROOT_MOUNT_REQUEST,
            b"production-data",
        ),
        environment_request_token=domain_digest(
            DigestDomain.ENVIRONMENT_INSTANCE,
            b"environment",
        ),
    )
    raw = canonical_json_bytes(request.model_dump(mode="json"))
    mislabeled_ref = record_ref(
        DigestDomain.RESOLUTION_REQUEST,
        raw,
        schema_version="polisyos.foundry.dependency-resolved-source-request.v1",
    )
    with pytest.raises(ValueError, match="schema version"):
        authority_module.load_strict_foundry_statement(
            record=mislabeled_ref,
            raw=raw,
        )
    with pytest.raises(TypeError, match="exact bytes"):
        authority_module.load_strict_foundry_statement(
            record=record_ref(
                DigestDomain.RESOLUTION_REQUEST,
                raw,
                schema_version=request.schema_version,
            ),
            raw=bytearray(raw),  # type: ignore[arg-type]
        )


def test_corrupted_digest_producer_is_rejected_by_independent_verifier() -> None:
    registry = decode_digest_domain_registry_toml(_DIGEST_REGISTRY.read_bytes())
    handler = authority_module.build_digest_domain_handlers(registry)[
        DigestDomain.RAW_BLOB
    ]
    expected = handler.produce(b"owner-bound-preimage")
    assert handler.verify(b"owner-bound-preimage", expected)

    def corrupt_producer(
        domain: DigestDomain,
        _preimage: bytes,
    ) -> DomainDigest[DigestDomain]:
        return domain_digest(domain, b"corrupt-producer-output")

    corrupted = replace(handler, producer=corrupt_producer)
    forged = corrupted.produce(b"owner-bound-preimage")
    assert not corrupted.verify(b"owner-bound-preimage", forged)

    corrupted_preimage = replace(
        handler,
        producer_preimage_builder=lambda _value: b"corrupt-preimage",
    )
    forged_from_bad_builder = corrupted_preimage.produce(b"owner-bound-preimage")
    assert not corrupted_preimage.verify(
        b"owner-bound-preimage",
        forged_from_bad_builder,
    )


def test_every_explicit_digest_builder_is_generated_from_registry_algebra() -> None:
    registry = decode_digest_domain_registry_toml(_DIGEST_REGISTRY.read_bytes())
    handlers = authority_module.build_digest_domain_handlers(registry)
    for row in registry.statement.domains:
        handler = handlers[row.domain_id]
        assert (
            handler.preimage_builder
            is authority_module.DIGEST_PREIMAGE_BUILDERS[row.algebra.preimage_kind]
        )
        assert (
            handler.verifier_preimage_builder
            is authority_module.DIGEST_VERIFIER_PREIMAGE_BUILDERS[
                row.algebra.preimage_kind
            ]
        )
        assert handler.producer is authority_module.DIGEST_PRODUCERS[
            row.algebra.producer_id
        ]
        assert handler.verifier is authority_module.DIGEST_VERIFIERS[
            row.algebra.verifier_id
        ]


def test_runtime_cutoff_composition_rejects_protocol_or_positive_fake_substitution() -> None:
    authority_module.validate_runtime_cutoff_constructor_bijection()
    authority_module.validate_production_owner_composition_bijection()


def test_candidate_runtime_evidence_does_not_substitute_for_missing_cutoff_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    candidate = authority_module.CandidateRuntimeEvidencePresent(
        status="present",
        evidence_ref=record_ref(
            DigestDomain.TOOLCHAIN_RUNTIME,
            b"candidate-only-runtime-observation",
            schema_version="polisyos.foundry.python-runtime-manifest.v1",
        ),
    )
    request = _authority_request(tmp_path, source_freeze=source_freeze)
    source = authority_module._ProductionCanonicalFoundrySourceAuthorityResolver().resolve(
        request=request
    )
    assert isinstance(source, authority_module.CanonicalFoundrySourceAuthority)
    try:
        with authority_module._unwrap_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        ) as source_payload:
            refusal = authority_module.build_runtime_cutoff_refusal(
                source_authority=source_payload,
                request=authority_module.DependencyAuthorityResolvedSourceRequestStatement(
                    schema_version=(
                        "polisyos.foundry.dependency-resolved-source-request.v1"
                    ),
                    pre_source_request=authority_module._pre_source_statement(request),
                    expected_source_tree_id=source_payload.statement.source_tree_id,
                ),
                candidate_runtime_evidence=candidate,
            )
    finally:
        authority_module._release_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        )

    assert refusal.preflight_refusal.failure.predicate_class == "not_established"
    assert refusal.preflight_refusal.failure.candidate_runtime_evidence == candidate
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(result, UnestablishedMethodCatalogDependencyProfile)
    _assert_current_cutoff_refusal(result)


def test_every_negative_variant_names_the_same_absent_receipt_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    current = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    moved = repo_root / "move.txt"
    moved.write_text("move\n", encoding="utf-8")
    _git_at(repo_root, "add", "--", moved.name)
    _git_at(repo_root, "commit", "-m", "move")
    rejected = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert current.preflight_refusal.persistence == rejected.persistence

    monkeypatch.setattr(authority_module, "_GIT_ROOT", tmp_path / "absent")
    unestablished = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert rejected.persistence == unestablished.persistence


def test_purpose_resolves_profile_without_caller_profile_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert "profile_id" not in MethodCatalogDependencyAuthorityRequest.model_fields
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(result, UnestablishedMethodCatalogDependencyProfile)
    _assert_current_cutoff_refusal(result)


def test_authority_record_pointer_round_trips_exact_live_artifact_id_wire() -> None:
    reference = record_ref(
        DigestDomain.RAW_BLOB,
        b"strict-live-artifact-id",
        schema_version="polisyos.foundry.raw-blob.v1",
    )
    assert str(authority_module._strict_artifact_id(reference)) == reference.artifact_id


@pytest.mark.parametrize(
    "wire",
    (
        "0" * 64,
        "sha256:" + "A" * 64,
        "SHA256:" + "0" * 64,
    ),
)
def test_bare_uppercase_or_unprefixed_artifact_id_fails_strict_parse(
    wire: str,
) -> None:
    valid = record_ref(
        DigestDomain.RAW_BLOB,
        b"strict-wire",
        schema_version="polisyos.foundry.raw-blob.v1",
    )
    with pytest.raises(ValidationError):
        type(valid)(
            artifact_id=wire,
            semantic_hash=valid.semantic_hash,
            schema_version=valid.schema_version,
        )


def test_signed_record_repository_has_no_verifier_injection_surface() -> None:
    parameters = inspect.signature(
        authority_module.FileSystemCASSignedRecordRepository
    ).parameters
    assert tuple(parameters) == ("store", "trust_resolver")
    assert "verifier" not in parameters


def test_profile_closure_names_root_extras_and_distribution_discriminant() -> None:
    profile = _resolve_tracked_profile()
    assert profile.declaration.root_distribution == "policy-engine"
    assert profile.declaration.extras == (
        "analytics",
        "bayesian",
        "ml",
        "optimization-advanced",
        "solvers",
    )
    assert profile.distributions
    assert profile.distribution_set.domain is DigestDomain.DISTRIBUTION_SET
    assert profile.stable_closure.domain is DigestDomain.DEPENDENCY_CLOSURE


def test_factory_holds_source_resolver_not_source_snapshot_and_resolves_each_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    calls = 0
    original = authority_module._ProductionCanonicalFoundrySourceAuthorityResolver.resolve

    def counted(
        self: object,
        *,
        request: MethodCatalogDependencyAuthorityRequest,
    ) -> object:
        nonlocal calls
        calls += 1
        return original(self, request=request)

    monkeypatch.setattr(
        authority_module._ProductionCanonicalFoundrySourceAuthorityResolver,
        "resolve",
        counted,
    )
    owner = build_production_method_catalog_dependency_authority()
    for _ in range(2):
        result = owner.resolve(_authority_request(tmp_path, source_freeze=source_freeze))
        assert isinstance(result, UnestablishedMethodCatalogDependencyProfile)
    assert calls == 2


def test_dirty_or_missing_source_returns_typed_variant_without_source_ref(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    authority_file = (
        product_root
        / "architecture"
        / "production_quality"
        / "method_catalog_dependency_authority.toml"
    )
    authority_file.unlink()
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert result.result_kind is NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED
    assert "source_authority_ref" not in result.model_dump(mode="json")


def test_negative_only_abi_rejects_positive_result_or_resolution_writer_codec_domain() -> None:
    authority_module.validate_negative_only_dependency_authority_abi()
    variants = set(
        authority_module.get_args(
            authority_module.get_args(
                authority_module.MethodCatalogDependencyAuthorityResult
            )[0]
        )
    )
    assert variants == {
        authority_module.SourceRejectedMethodCatalogDependencyProfile,
        authority_module.SourceUnestablishedMethodCatalogDependencyProfile,
        authority_module.UnestablishedMethodCatalogDependencyProfile,
    }


def test_negative_stage_map_fixes_status_predicate_code_domains_source_ref_and_persistence() -> None:
    assert set(authority_module.SOURCE_BOOTSTRAP_FAILURE_STAGES) == {
        NegativeDependencyAuthorityResultKind.SOURCE_REJECTED,
        NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED,
    }
    for row in authority_module.SOURCE_BOOTSTRAP_FAILURE_STAGES.values():
        assert row.predicate_id is AuthorityPredicateId.SOURCE_FREEZE
        assert row.source_ref_rule == "forbidden"
        assert row.persistence == "not_established"
        assert row.persistence_capability == "owner_resolved_resolution_receipt_store"


def test_runtime_cutoff_predicate_is_one_sided_and_cutoff_specific() -> None:
    registry = authority_module.load_digest_domain_registry(
        authority_module._DIGEST_REGISTRY_PATH
    )
    one_sided = tuple(
        row for row in registry.statement.predicates if row.branch_shape == "not_established_only"
    )
    assert len(one_sided) == 1
    assert one_sided[0].predicate_id is AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF
    assert (
        one_sided[0].not_established_code
        is AuthorityFailureCode.RUNTIME_SUBTREE_CUTOFF_NOT_ESTABLISHED
    )


def test_ambient_registry_mutation_after_source_capability_cannot_change_cutoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    request = _authority_request(tmp_path, source_freeze=source_freeze)
    source = authority_module._build_production_canonical_source_resolver().resolve(
        request=request
    )
    assert isinstance(source, authority_module.CanonicalFoundrySourceAuthority)
    digest_registry = (
        product_root
        / "architecture"
        / "production_quality"
        / "method_catalog_dependency_digest_domains.toml"
    )
    digest_registry.write_text("corrupt after mint\n", encoding="utf-8")
    try:
        with authority_module._unwrap_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        ) as payload:
            result = authority_module.build_runtime_cutoff_refusal(
                source_authority=payload,
                request=authority_module.DependencyAuthorityResolvedSourceRequestStatement(
                    schema_version=(
                        "polisyos.foundry.dependency-resolved-source-request.v1"
                    ),
                    pre_source_request=authority_module._pre_source_statement(request),
                    expected_source_tree_id=payload.statement.source_tree_id,
                ),
                candidate_runtime_evidence=authority_module.CandidateRuntimeEvidenceNotRequested(
                    status="not_requested",
                    reason="owner_enforced_runtime_subtree_cutoff_absent",
                ),
            )
            _assert_current_cutoff_refusal(result)
    finally:
        authority_module._release_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        )


def test_missing_unreadable_or_corrupt_digest_registry_returns_source_not_established(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    registry = (
        product_root
        / "architecture"
        / "production_quality"
        / "method_catalog_dependency_digest_domains.toml"
    )
    registry.write_bytes(b"not = [valid")
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert result.result_kind is NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED


def test_unusable_git_root_or_unresolvable_commit_returns_source_not_established_without_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(authority_module, "_GIT_ROOT", tmp_path / "not-a-repository")
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze="f" * 40)
    )
    assert result.result_kind is NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED
    assert "expected_source_tree_id" not in result.request.model_dump(mode="json")


def test_source_rejection_binds_request_commit_tree_to_owner_observed_head_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root, _product_root, old_commit = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    old_tree = _git_at(repo_root, "rev-parse", f"{old_commit}^{{tree}}")
    marker = repo_root / "advance.txt"
    marker.write_text("advance\n", encoding="utf-8")
    _git_at(repo_root, "add", "--", marker.name)
    _git_at(repo_root, "commit", "-m", "advance")
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=old_commit)
    )
    assert result.request.expected_source_tree_id == old_tree
    assert result.failure.expected_source_freeze_commit == old_commit
    assert result.failure.owner_observed_head_commit == _git_at(repo_root, "rev-parse", "HEAD")
    assert result.failure.owner_observed_tree_id != old_tree


def test_unrelated_unequal_source_hashes_cannot_satisfy_source_freeze_rejection() -> None:
    request = authority_module.DependencyAuthorityResolvedSourceRequestStatement(
        schema_version="polisyos.foundry.dependency-resolved-source-request.v1",
        pre_source_request=authority_module.DependencyAuthorityPreSourceRequestStatement(
            schema_version="polisyos.foundry.dependency-pre-source-request.v1",
            authority_purpose="n8_method_catalog_reconstruction",
            expected_source_freeze_commit="1" * 40,
            production_data_request_token=domain_digest(
                DigestDomain.ROOT_MOUNT_REQUEST,
                b"root",
            ),
            environment_request_token=domain_digest(
                DigestDomain.ENVIRONMENT_INSTANCE,
                b"environment",
            ),
        ),
        expected_source_tree_id="2" * 40,
    )
    with pytest.raises(ValueError, match="request.*source|source.*request"):
        authority_module.SourceRejectedMethodCatalogDependencyProfile(
            result_kind=NegativeDependencyAuthorityResultKind.SOURCE_REJECTED,
            status="rejected",
            persistence=authority_module.NegativeResultPersistenceDisposition(
                status="not_established",
                missing_capability="owner_resolved_resolution_receipt_store",
                missing_capability_state="absent/unallocated",
            ),
            request=request,
            failure=authority_module.SourceFreezeRejectedPredicate(
                status="rejected",
                predicate_id=AuthorityPredicateId.SOURCE_FREEZE,
                predicate_class="recomputed",
                failure_code=AuthorityFailureCode.SOURCE_FREEZE_MISMATCH,
                expected_source_freeze_commit="3" * 40,
                expected_source_tree_id="4" * 40,
                owner_observed_head_commit="5" * 40,
                owner_observed_tree_id="6" * 40,
                observation_producer="canonical_module_git_recompute_v1",
            ),
        )


def test_cutoff_absence_uses_cutoff_predicate_not_python_runtime_evidence_predicate() -> None:
    predicate = authority_module._NoRuntimeSubtreeCutoffAuthority().preflight()
    assert predicate.predicate_id is AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF
    assert predicate.predicate_id is not AuthorityPredicateId.PYTHON_RUNTIME
    assert predicate.candidate_runtime_evidence.status == "not_requested"


def test_cutoff_outer_owner_returns_exact_unpersisted_refusal_before_any_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    environment = tmp_path / "environment"
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(result, UnestablishedMethodCatalogDependencyProfile)
    assert not environment.exists()
    assert result.preflight_refusal.persistence.status == "not_established"


def test_cutoff_refusal_names_absent_owner_resolved_receipt_store() -> None:
    gap = authority_module._persistence_gap()
    assert gap.missing_capability == "owner_resolved_resolution_receipt_store"
    assert gap.missing_capability_state == "absent/unallocated"


def test_cwd_cas_and_signing_environment_do_not_create_or_redirect_refusal_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    decoy = tmp_path / "decoy-cas"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("POLISYOS_ARTIFACT_ROOT", str(decoy))
    monkeypatch.setenv("POLISYOS_SIGNING_KEY", "candidate-only")
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(result, UnestablishedMethodCatalogDependencyProfile)
    assert not decoy.exists()


def test_no_persisted_schema_transitively_contains_owner_capability() -> None:
    authority_module.validate_no_owner_capability_in_persisted_schemas()


def test_every_authority_scalar_has_semantic_role_without_name_heuristic() -> None:
    authority_module.validate_authority_scalar_role_coverage()


def test_unregistered_decisive_digest_or_predicate_fails_generic_coverage() -> None:
    authority_module.validate_decisive_domain_coverage()
    authority_module.validate_authority_predicate_coverage()


def test_source_derived_owner_boundary_classes_exactly_determine_protocol_pairs() -> None:
    pairs = authority_module.derive_owner_protocol_concrete_pairs_from_source(
        module_file=Path(authority_module.__file__),
        namespace=vars(authority_module),
    )
    assert pairs == authority_module._OWNER_PROTOCOL_CONCRETE_PAIRS
    assert len(pairs) == 12


def test_source_derived_owner_entrypoint_denominator_equals_wrapped_methods() -> None:
    rows = authority_module.derive_owner_entrypoint_denominator_from_source(
        module_file=Path(authority_module.__file__),
        protocol_concrete_pairs=authority_module._OWNER_PROTOCOL_CONCRETE_PAIRS,
    )
    assert len(rows) == len(authority_module._OWNER_ENTRYPOINT_SPECS)
    for row in rows:
        target = row.target
        function = (
            target.concrete_owner_type.__dict__[target.method_name]
            if isinstance(target, authority_module.OwnerMethodTarget)
            else vars(authority_module)[target.function_name]
        )
        assert function.__gy_n12_owner_guard__ == row


def test_new_owner_boundary_or_removed_protocol_base_fails_pair_derivation(
    tmp_path: Path,
) -> None:
    source = Path(authority_module.__file__).read_text(encoding="utf-8")
    mutant = tmp_path / "dependency_authority.py"
    mutant.write_text(
        source + "\nclass _RogueOwner(_OwnerBoundaryBase):\n    pass\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="denominators differ"):
        authority_module.derive_owner_protocol_concrete_pairs_from_source(
            module_file=mutant,
            namespace=vars(authority_module),
        )


def test_removing_one_derived_method_or_function_guard_fails_independent_bijection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = authority_module._ProductionDataMountResolver.__dict__["read_manifest"]
    monkeypatch.delattr(target, "__gy_n12_owner_guard__")
    with pytest.raises(AssertionError, match="guard denominator"):
        authority_module.validate_owner_entrypoint_failure_mapping()


def test_owner_borrow_repeated_operator_occurrences_are_indexed_and_reconciled() -> None:
    rows = authority_module.derive_owner_borrow_reachability_from_source(
        module_file=Path(authority_module.__file__),
        owner_entrypoints=authority_module._OWNER_ENTRYPOINT_SPECS,
    )
    for row in rows:
        ids = tuple(node.occurrence_id for node in row.evaluated_nodes)
        assert len(ids) == len(set(ids))


def _derive_mutated_owner_borrow_graph(tmp_path: Path, suffix: str) -> object:
    mutant = tmp_path / "dependency_authority.py"
    mutant.write_text(
        Path(authority_module.__file__).read_text(encoding="utf-8") + suffix,
        encoding="utf-8",
    )
    return authority_module.derive_owner_borrow_reachability_from_source(
        module_file=mutant,
        owner_entrypoints=authority_module._OWNER_ENTRYPOINT_SPECS,
    )


def test_bare_unwrap_or_fork_inside_owner_borrow_fails_source_denominator(
    tmp_path: Path,
) -> None:
    mutations = (
        "\ndef gy_bare(token):\n"
        "    return _unwrap_owner_capability(token, _CANONICAL_SOURCE_SPEC)\n",
        "\ndef gy_fork(token):\n"
        "    with _unwrap_owner_capability(token, _CANONICAL_SOURCE_SPEC) as payload:\n"
        "        os.fork()\n",
    )
    for index, mutation in enumerate(mutations):
        case_root = tmp_path / str(index)
        case_root.mkdir()
        with pytest.raises(AssertionError, match="bare unwrap|process primitive"):
            _derive_mutated_owner_borrow_graph(case_root, mutation)


def test_owner_borrow_helper_to_fork_fails_transitive_call_graph(tmp_path: Path) -> None:
    suffix = (
        "\ndef gy_helper_to_fork(value):\n"
        "    del value\n"
        "    os.fork()\n"
        "\ndef gy_borrow_calls_helper(token):\n"
        "    with _unwrap_owner_capability(token, _CANONICAL_SOURCE_SPEC) as payload:\n"
        "        gy_helper_to_fork(payload)\n"
    )
    with pytest.raises(AssertionError, match="process primitive"):
        _derive_mutated_owner_borrow_graph(tmp_path, suffix)


def test_owner_borrow_callback_or_helper_cannot_store_or_return_payload(
    tmp_path: Path,
) -> None:
    suffix = (
        "\n_GY_ESCAPE = []\n"
        "\ndef gy_store(value):\n"
        "    _GY_ESCAPE.append(value)\n"
        "\ndef gy_return(value):\n"
        "    return value\n"
        "\ndef gy_borrow_callback(token):\n"
        "    with _unwrap_owner_capability(token, _CANONICAL_SOURCE_SPEC) as payload:\n"
        "        gy_store(payload)\n"
        "        gy_return(payload)\n"
    )
    with pytest.raises(AssertionError, match="escapes"):
        _derive_mutated_owner_borrow_graph(tmp_path, suffix)


def test_owner_borrow_custom_len_to_fork_fails_implicit_dispatch_graph(
    tmp_path: Path,
) -> None:
    suffix = (
        "\ndef gy_len(value):\n"
        "    return len(value)\n"
        "\ndef gy_borrow_len(token):\n"
        "    with _unwrap_owner_capability(token, _CANONICAL_SOURCE_SPEC) as payload:\n"
        "        gy_len(payload)\n"
    )
    with pytest.raises(AssertionError, match="implicit dispatch"):
        _derive_mutated_owner_borrow_graph(tmp_path, suffix)


def test_owner_borrow_custom_iter_to_aliased_spawn_fails_implicit_dispatch_graph(
    tmp_path: Path,
) -> None:
    suffix = (
        "\n_GY_SPAWN = subprocess.Popen\n"
        "\ndef gy_iter(value):\n"
        "    for _member in value:\n"
        "        _GY_SPAWN(['/usr/bin/true'])\n"
        "\ndef gy_borrow_iter(token):\n"
        "    with _unwrap_owner_capability(token, _CANONICAL_SOURCE_SPEC) as payload:\n"
        "        gy_iter(payload)\n"
    )
    with pytest.raises(AssertionError, match="implicit dispatch|process primitive"):
        _derive_mutated_owner_borrow_graph(tmp_path, suffix)


def test_owner_borrow_descriptor_getter_to_callback_fails_implicit_dispatch_graph(
    tmp_path: Path,
) -> None:
    suffix = (
        "\n_GY_DESCRIPTOR_ESCAPE = []\n"
        "\ndef gy_sink(value):\n"
        "    _GY_DESCRIPTOR_ESCAPE.append(value)\n"
        "\ndef gy_descriptor(value, callback):\n"
        "    callback(value.source_root.descriptor)\n"
        "\ndef gy_borrow_descriptor(token):\n"
        "    with _unwrap_owner_capability(token, _CANONICAL_SOURCE_SPEC) as payload:\n"
        "        gy_descriptor(payload, gy_sink)\n"
    )
    with pytest.raises(AssertionError, match="escapes|implicit dispatch"):
        _derive_mutated_owner_borrow_graph(tmp_path, suffix)


def test_owner_borrow_if_custom_bool_to_fork_fails_statement_dispatch_graph(
    tmp_path: Path,
) -> None:
    suffix = (
        "\ndef gy_bool(value):\n"
        "    if value:\n"
        "        os.fork()\n"
        "\ndef gy_borrow_bool(token):\n"
        "    with _unwrap_owner_capability(token, _CANONICAL_SOURCE_SPEC) as payload:\n"
        "        gy_bool(payload)\n"
    )
    with pytest.raises(AssertionError, match="implicit dispatch|process primitive"):
        _derive_mutated_owner_borrow_graph(tmp_path, suffix)


def test_owner_borrow_sequence_match_to_spawn_fails_pattern_dispatch_graph(
    tmp_path: Path,
) -> None:
    suffix = (
        "\ndef gy_match(value):\n"
        "    match value:\n"
        "        case [*_members]:\n"
        "            subprocess.Popen(['/usr/bin/true'])\n"
        "\ndef gy_borrow_match(token):\n"
        "    with _unwrap_owner_capability(token, _CANONICAL_SOURCE_SPEC) as payload:\n"
        "        gy_match(payload)\n"
    )
    with pytest.raises(AssertionError, match="implicit dispatch|process primitive"):
        _derive_mutated_owner_borrow_graph(tmp_path, suffix)


def test_owner_borrow_len_of_exact_builtin_tuple_is_admitted_control(
    tmp_path: Path,
) -> None:
    suffix = (
        "\ndef gy_tuple_len(value):\n"
        "    return len(value.digest_registry.statement.domains)\n"
        "\ndef gy_borrow_tuple_len(token):\n"
        "    with _unwrap_owner_capability(token, _CANONICAL_SOURCE_SPEC) as payload:\n"
        "        gy_tuple_len(payload)\n"
    )
    rows = _derive_mutated_owner_borrow_graph(tmp_path, suffix)
    assert rows


def _predicate_evidence_refs(
    domains: tuple[DigestDomain, ...],
) -> tuple[authority_module.FoundryRecordRef[DigestDomain], ...]:
    return tuple(
        record_ref(
            domain,
            domain.value.encode(),
            schema_version=f"polisyos.foundry.{domain.value}.v1",
        )
        for domain in domains
    )


def test_post_source_negative_stage_map_derives_code_and_evidence_from_canonical_predicate_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(result, UnestablishedMethodCatalogDependencyProfile)
    registry = decode_digest_domain_registry_toml(_DIGEST_REGISTRY.read_bytes())
    row = next(
        item
        for item in registry.statement.predicates
        if item.predicate_id is AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF
    )
    failure = result.preflight_refusal.failure
    assert row.branch_shape == "not_established_only"
    assert failure.failure_code is row.not_established_code
    assert failure.missing_capability == row.not_established_requirement.capability_id
    assert (
        failure.missing_capability_state
        == row.not_established_requirement.capability_state
    )


def test_cutoff_row_rejects_admitted_class_or_satisfied_disposition() -> None:
    raw = _DIGEST_REGISTRY.read_bytes()
    needle = (
        b'predicate_id = "owner_enforced_runtime_subtree_cutoff"\n'
    )
    mutated = raw.replace(
        needle,
        needle + b'admitted_classes = ["recomputed"]\n',
        1,
    )
    with pytest.raises(ValueError, match="alternate branch fields"):
        decode_digest_domain_registry_toml(mutated)

    registry = decode_digest_domain_registry_toml(raw)
    cutoff = next(
        item
        for item in registry.statement.predicates
        if item.predicate_id is AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF
    )
    with pytest.raises(ValidationError):
        SatisfiedAuthorityPredicate.model_validate(
            {
                "branch_shape": "bidirectional",
                "status": "satisfied",
                "predicate_registry_ref": registry.registry_ref,
                "predicate_spec": cutoff,
                "predicate_id": cutoff.predicate_id,
                "predicate_class": "recomputed",
                "evidence_refs": (registry.registry_ref,),
            },
            strict=True,
        )


def test_bidirectional_predicate_branch_remains_constructible() -> None:
    registry = decode_digest_domain_registry_toml(_DIGEST_REGISTRY.read_bytes())
    row = next(
        item
        for item in registry.statement.predicates
        if item.predicate_id is AuthorityPredicateId.AUTHORITY_REGISTRY
    )
    assert isinstance(row, BidirectionalAuthorityPredicateSpec)
    assert isinstance(row.satisfied_requirement, DomainEvidenceRequirement)
    assert isinstance(row.rejected_requirement, DomainEvidenceRequirement)
    assert isinstance(row.not_established_requirement, MissingEvidenceDomainsRequirement)

    satisfied = SatisfiedAuthorityPredicate(
        branch_shape="bidirectional",
        status="satisfied",
        predicate_registry_ref=registry.registry_ref,
        predicate_spec=row,
        predicate_id=row.predicate_id,
        predicate_class="recomputed",
        evidence_refs=_predicate_evidence_refs(
            row.satisfied_requirement.evidence_domains
        ),
    )
    rejected = RejectedAuthorityPredicate(
        branch_shape="bidirectional",
        status="rejected",
        predicate_registry_ref=registry.registry_ref,
        predicate_spec=row,
        predicate_id=row.predicate_id,
        predicate_class="recomputed",
        failure_code=row.rejected_code,
        evidence_refs=_predicate_evidence_refs(
            row.rejected_requirement.evidence_domains
        ),
    )
    unestablished = BidirectionalUnestablishedAuthorityPredicate(
        branch_shape="bidirectional",
        status="not_established",
        predicate_registry_ref=registry.registry_ref,
        predicate_spec=row,
        predicate_id=row.predicate_id,
        predicate_class="not_established",
        failure_code=row.not_established_code,
        missing_domains=row.not_established_requirement.missing_domains,
    )
    assert {satisfied.status, rejected.status, unestablished.status} == {
        "satisfied",
        "rejected",
        "not_established",
    }


def test_sibling_cutoff_result_constructor_enlarges_constructor_denominator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = Path(authority_module.__file__).read_text(encoding="utf-8")
    mutant = ast.parse(
        source
        + "\ndef sibling_cutoff_constructor():\n"
        + "    return RuntimeCutoffPreflightRefusal()\n"
    )
    monkeypatch.setattr(authority_module, "_module_ast", lambda: mutant)
    with pytest.raises(AssertionError, match="constructor denominator"):
        authority_module.validate_runtime_cutoff_constructor_bijection()


def test_source_stage_cannot_carry_appointment_failure_with_valid_result_kind() -> None:
    with pytest.raises(ValidationError):
        authority_module.SourceFreezeRejectedPredicate.model_validate(
            {
                "status": "rejected",
                "predicate_id": AuthorityPredicateId.PRODUCTION_APPOINTMENT,
                "predicate_class": "recomputed",
                "failure_code": AuthorityFailureCode.APPOINTMENT_MISMATCH,
                "expected_source_freeze_commit": "1" * 40,
                "expected_source_tree_id": "2" * 40,
                "owner_observed_head_commit": "3" * 40,
                "owner_observed_tree_id": "4" * 40,
                "observation_producer": "canonical_module_git_recompute_v1",
            },
            strict=True,
        )


def test_negative_production_graph_rejects_runtime_installation_owner_edge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = Path(authority_module.__file__).read_text(encoding="utf-8")
    mutant = ast.parse(
        source
        + "\nclass _ProductionMethodCatalogDependencyAuthority:\n"
        + "    def resolve(self):\n"
        + "        _open_owner_python_runtime_installation_authority()\n"
    )
    monkeypatch.setattr(authority_module, "_module_ast", lambda: mutant)
    with pytest.raises(AssertionError, match="candidate machinery"):
        authority_module.validate_production_owner_composition_bijection()


def test_every_missing_capability_literal_has_one_exact_incomplete_state_label(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(result, UnestablishedMethodCatalogDependencyProfile)
    pairs = {
        (
            result.preflight_refusal.failure.missing_capability,
            result.preflight_refusal.failure.missing_capability_state,
        ),
        (
            result.preflight_refusal.persistence.missing_capability,
            result.preflight_refusal.persistence.missing_capability_state,
        ),
    }
    assert pairs == {
        ("owner_enforced_runtime_subtree_cutoff", "absent/unallocated"),
        ("owner_resolved_resolution_receipt_store", "absent/unallocated"),
    }


def test_owner_capabilities_have_no_wire_codec_and_fresh_process_reresolves() -> None:
    token_types = {
        value
        for value in vars(authority_module).values()
        if isinstance(value, type)
        and vars(value).get("__owner_token_class_marker__")
        is authority_module._OWNER_TOKEN_CLASS_MARKER
    }
    codec_types = {
        model
        for codec in authority_module.FOUNDRY_STATEMENT_CODECS.values()
        for model in codec.statement_types
    }
    assert token_types.isdisjoint(codec_types)
    forged = object.__new__(authority_module.CanonicalFoundrySourceAuthority)
    with (
        pytest.raises(
            authority_module.OwnerCapabilityFault,
            match="unminted_token",
        ),
        authority_module._unwrap_owner_capability(
            forged,
            authority_module._CANONICAL_SOURCE_SPEC,
        ),
    ):
        pass


def test_unknown_authority_dto_field_fails_strict_parse() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MethodCatalogDependencyAuthorityRequest.model_validate(
            {
                "authority_purpose": "n8_method_catalog_reconstruction",
                "expected_source_freeze_commit": "1" * 40,
                "production_data_root": {"value": Path("/appointed")},
                "environment_root": {"value": Path("/environment")},
                "caller_asserted_authority": True,
            },
            strict=True,
        )


def test_source_mismatch_requires_same_domain_expected_and_observed() -> None:
    with pytest.raises(ValueError, match="share one semantic domain"):
        DigestPredicateMismatch(
            kind="digest_mismatch",
            predicate_id=AuthorityPredicateId.SOURCE_FREEZE,
            code=AuthorityFailureCode.SOURCE_FREEZE_MISMATCH,
            expected=domain_digest(DigestDomain.CANONICAL_SOURCE, b"expected"),
            observed=domain_digest(DigestDomain.PROFILE_DECLARATION, b"observed"),
            predicate_class="recomputed",
        )


def test_scalar_mismatch_rejects_cross_domain_strings() -> None:
    with pytest.raises(ValueError, match="share one semantic domain"):
        ScalarPredicateMismatch(
            kind="scalar_mismatch",
            predicate_id=AuthorityPredicateId.PURPOSE_PROFILE,
            code=AuthorityFailureCode.PROFILE_MISMATCH,
            expected=DomainScalar(domain=ScalarDomain.PROFILE_ID, value="same-shape"),
            observed=DomainScalar(domain=ScalarDomain.VERSION, value="other-shape"),
            predicate_class="recomputed",
        )


def test_every_mismatch_code_rejects_equal_or_incompatible_field_shapes() -> None:
    for code in AuthorityFailureCode:
        with pytest.raises(ValueError, match="must differ"):
            DigestPredicateMismatch(
                kind="digest_mismatch",
                predicate_id=AuthorityPredicateId.SOURCE_FREEZE,
                code=code,
                expected=domain_digest(DigestDomain.RAW_BLOB, b"same"),
                observed=domain_digest(DigestDomain.RAW_BLOB, b"same"),
                predicate_class="recomputed",
            )
        with pytest.raises(ValueError, match="share one semantic domain"):
            ScalarPredicateMismatch(
                kind="scalar_mismatch",
                predicate_id=AuthorityPredicateId.PURPOSE_PROFILE,
                code=code,
                expected=DomainScalar(domain=ScalarDomain.PROFILE_ID, value="a"),
                observed=DomainScalar(domain=ScalarDomain.VERSION, value="b"),
                predicate_class="recomputed",
            )


def _c1_ref(
    domain: DigestDomain,
    label: str,
) -> authority_module.FoundryRecordRef[DigestDomain]:
    return record_ref(
        domain,
        label.encode("utf-8"),
        schema_version=f"polisyos.foundry.{domain.value}.v1",
    )


def _c1_external_ref(
    kind: authority_module.ExternalAuthorityKind,
    label: str,
) -> authority_module.evidence_module.ExternalAuthorityRef[
    authority_module.ExternalAuthorityKind
]:
    return authority_module.evidence_module.ExternalAuthorityRef[
        authority_module.ExternalAuthorityKind
    ](
        authority_kind=kind,
        value=label,
        resolver_appointment_ref=domain_digest(
            DigestDomain.VERIFIER_APPOINTMENT,
            f"resolver:{label}".encode(),
        ),
    )


def _c1_appointment_pair(
    *,
    root_label: str,
    custodian_label: str,
    manifest_label: str,
) -> tuple[
    authority_module.ProductionDataInputAppointmentStatement,
    authority_module.ProductionDataCustodyStatement,
]:
    root = _c1_external_ref(
        authority_module.ExternalAuthorityKind.INSTITUTIONAL_ROOT,
        root_label,
    )
    custodian = _c1_external_ref(
        authority_module.ExternalAuthorityKind.PRODUCTION_DATA_CUSTODIAN,
        custodian_label,
    )
    manifest_ref = _c1_ref(DigestDomain.PRODUCTION_MANIFEST, manifest_label)
    custody = authority_module.ProductionDataCustodyStatement(
        schema_version="polisyos.foundry.production-data-custody.v1",
        institutional_root=root,
        appointed_custodian=custodian,
        manifest_ref=manifest_ref,
        access_mode="read_only",
        writer_access_disposition="denied",
    )
    custody_ref = record_ref(
        DigestDomain.PRODUCTION_CUSTODY,
        canonical_json_bytes(custody.model_dump(mode="json")),
        schema_version=custody.schema_version,
    )
    appointment = authority_module.ProductionDataInputAppointmentStatement(
        schema_version="polisyos.foundry.production-data-appointment.v1",
        authority_purpose="n8_method_catalog_reconstruction",
        appointed_root=root,
        manifest_relative_path="manifest.json",
        expected_manifest_ref=manifest_ref,
        appointed_custodian=custodian,
        custody_statement_ref=custody_ref,
        trust_policy_ref=_c1_ref(DigestDomain.TRUST_POLICY, "policy"),
    )
    return appointment, custody


def test_two_authentic_appointment_custody_pairs_cannot_be_cross_swapped() -> None:
    pair_a = _c1_appointment_pair(
        root_label="root-a",
        custodian_label="custodian-a",
        manifest_label="manifest-a",
    )
    pair_b = _c1_appointment_pair(
        root_label="root-b",
        custodian_label="custodian-b",
        manifest_label="manifest-b",
    )
    authority_module.validate_appointment_custody_pair(*pair_a)
    authority_module.validate_appointment_custody_pair(*pair_b)
    with pytest.raises(ValueError, match="appointment.*custody"):
        authority_module.validate_appointment_custody_pair(pair_a[0], pair_b[1])


def test_authentic_appointment_for_root_a_rejects_requested_root_b_before_mount() -> None:
    appointment, custody = _c1_appointment_pair(
        root_label="root-a",
        custodian_label="custodian-a",
        manifest_label="manifest-a",
    )
    authority_module.validate_appointment_custody_pair(appointment, custody)
    requested_root_b = _c1_external_ref(
        authority_module.ExternalAuthorityKind.INSTITUTIONAL_ROOT,
        "root-b",
    )
    with pytest.raises(ValueError, match="requested institutional root"):
        authority_module.validate_appointment_requested_root(
            appointment,
            requested_root_b,
        )


def _c1_root_challenge(
    *,
    nonce_label: str,
    manifest_label: str,
) -> authority_module.ProductionDataRootAccessChallenge:
    return authority_module.ProductionDataRootAccessChallenge(
        schema_version="polisyos.foundry.root-access-challenge.v1",
        request_ref=_c1_ref(DigestDomain.RESOLUTION_REQUEST, "request"),
        challenge_nonce=domain_digest(DigestDomain.ROOT_NONCE, nonce_label.encode()),
        expected_root=_c1_external_ref(
            authority_module.ExternalAuthorityKind.INSTITUTIONAL_ROOT,
            "root-a",
        ),
        expected_manifest_ref=_c1_ref(
            DigestDomain.PRODUCTION_MANIFEST,
            manifest_label,
        ),
        mount_resolution_ref=_c1_ref(
            DigestDomain.ROOT_MOUNT_RESOLUTION,
            "mount-a",
        ),
    )


def _c1_root_attestation(
    challenge: authority_module.ProductionDataRootAccessChallenge,
) -> authority_module.RootAccessAttestationStatement:
    challenge_ref = record_ref(
        DigestDomain.ROOT_CHALLENGE,
        canonical_json_bytes(challenge.model_dump(mode="json")),
        schema_version=challenge.schema_version,
    )
    return authority_module.RootAccessAttestationStatement(
        schema_version="polisyos.foundry.root-access-attestation.v1",
        challenge_ref=challenge_ref,
        request_ref=challenge.request_ref,
        challenge_nonce=challenge.challenge_nonce,
        institutional_root=challenge.expected_root,
        observed_manifest_ref=challenge.expected_manifest_ref,
        mount_resolution_ref=challenge.mount_resolution_ref,
        access_mode="read_only",
        writer_access_disposition="denied",
    )


def test_candidate_evidence_binds_fresh_challenge_and_current_manifest() -> None:
    challenge = _c1_root_challenge(
        nonce_label="fresh-nonce",
        manifest_label="current-manifest",
    )
    attestation = _c1_root_attestation(challenge)
    authority_module.validate_root_access_attestation(challenge, attestation)

    changed_manifest = _c1_root_challenge(
        nonce_label="fresh-nonce",
        manifest_label="later-manifest",
    )
    with pytest.raises(ValueError, match="root-access attestation"):
        authority_module.validate_root_access_attestation(
            changed_manifest,
            attestation,
        )


def test_old_signed_root_attestation_cannot_relabel_fresh_nonce() -> None:
    historical = _c1_root_challenge(
        nonce_label="historical-nonce",
        manifest_label="manifest",
    )
    later = _c1_root_challenge(
        nonce_label="later-nonce",
        manifest_label="manifest",
    )
    with pytest.raises(ValueError, match="root-access attestation"):
        authority_module.validate_root_access_attestation(
            later,
            _c1_root_attestation(historical),
        )


def test_root_nonce_and_challenge_statement_domains_are_not_substitutable() -> None:
    challenge = _c1_root_challenge(
        nonce_label="nonce",
        manifest_label="manifest",
    )
    wrong_nonce = challenge.model_dump(mode="json")
    wrong_nonce["challenge_nonce"] = _c1_ref(
        DigestDomain.ROOT_CHALLENGE,
        "challenge",
    ).semantic_hash.model_dump(mode="json")
    with pytest.raises(ValidationError, match="root-access-nonce"):
        authority_module.ProductionDataRootAccessChallenge.model_validate(
            wrong_nonce,
            strict=True,
        )


def test_source_trust_bootstrap_rejects_pem_or_wrong_length_root_key() -> None:
    raw = b"k" * 32
    good = TrustPublicKey(
        key_id="sha256:" + hashlib.sha256(raw).hexdigest(),
        algorithm="ed25519",
        public_key_encoding="raw-ed25519-32",
        public_key_bytes=raw,
        signer_identity="foundry-root",
        roles=(TrustRole.FOUNDRY_TRUST_ROOT,),
    )
    assert len(good.public_key_bytes) == 32
    for invalid in (b"short", b"-----BEGIN PUBLIC KEY-----\n" + raw):
        with pytest.raises(ValidationError):
            TrustPublicKey(
                key_id="sha256:" + hashlib.sha256(invalid).hexdigest(),
                algorithm="ed25519",
                public_key_encoding="raw-ed25519-32",
                public_key_bytes=invalid,
                signer_identity="foundry-root",
                roles=(TrustRole.FOUNDRY_TRUST_ROOT,),
            )


def _c1_trust_material(
    *keys: TrustPublicKey,
) -> authority_module.evidence_module.TrustMaterialStatement:
    return authority_module.evidence_module.TrustMaterialStatement(
        schema_version="polisyos.foundry.trust-material.v1",
        signature_profile="polisyos.ed25519.detached.v1",
        keys=tuple(sorted(keys, key=lambda row: row.key_id)),
        revocation_refs=(),
        effective_admission_ref=_c1_ref(
            DigestDomain.PROFILE_ADMISSION,
            "admission",
        ),
    )


def _c1_resolved_key(
    label: bytes,
    role: TrustRole,
) -> authority_module.evidence_module.ResolvedTrustKey:
    return authority_module.evidence_module.ResolvedTrustKey(
        key_id="sha256:" + hashlib.sha256(label).hexdigest(),
        signer_identity=f"signer-{label.decode()}",
        selected_role=role,
    )


def test_trust_resolution_rejects_absent_identity_or_extra_eligible_key() -> None:
    key_bytes = b"a" * 32
    key = TrustPublicKey(
        key_id="sha256:" + hashlib.sha256(key_bytes).hexdigest(),
        algorithm="ed25519",
        public_key_encoding="raw-ed25519-32",
        public_key_bytes=key_bytes,
        signer_identity="signer-a",
        roles=(TrustRole.APPOINTMENT_ISSUER,),
    )
    material = _c1_trust_material(key)
    material_ref = record_ref(
        DigestDomain.TRUST_MATERIAL,
        canonical_json_bytes(material.model_dump(mode="json")),
        schema_version=material.schema_version,
    )
    receipt = authority_module.evidence_module.TrustResolutionReceiptStatement(
        schema_version="polisyos.foundry.trust-resolution.v1",
        source_authority_ref=_c1_ref(DigestDomain.CANONICAL_SOURCE, "source"),
        source_freeze_commit="1" * 40,
        trust_policy_ref=_c1_ref(DigestDomain.TRUST_POLICY, "policy"),
        required_role=TrustRole.APPOINTMENT_ISSUER,
        trust_material_ref=material_ref,
        eligible_keys=(
            authority_module.evidence_module.ResolvedTrustKey(
                key_id=key.key_id,
                signer_identity=key.signer_identity,
                selected_role=TrustRole.APPOINTMENT_ISSUER,
            ),
            _c1_resolved_key(b"b", TrustRole.APPOINTMENT_ISSUER),
        ),
        revocation_dispositions=(),
        verifier_provenance_ref=_c1_ref(
            DigestDomain.VERIFIER_PROVENANCE,
            "verifier",
        ),
    )
    with pytest.raises(ValueError, match="eligible trust key denominator"):
        authority_module.validate_trust_resolution_receipt(receipt, material)
    with pytest.raises(ValidationError):
        TrustPublicKey(
            key_id=key.key_id,
            algorithm="ed25519",
            public_key_encoding="raw-ed25519-32",
            public_key_bytes=key_bytes,
            signer_identity="",
            roles=(TrustRole.APPOINTMENT_ISSUER,),
        )


def test_synonym_named_raw_path_field_fails_generic_schema_coverage() -> None:
    class _RogueAuthorityPathCarrier(FoundryAuthorityModel):
        payload_location: Path

    with pytest.raises(AssertionError, match="payload_location"):
        authority_module.validate_authority_scalar_role_coverage()


def test_runtime_receipt_does_not_claim_writer_independent_continuous_immutability() -> None:
    fields = set(
        authority_module.evidence_module.PythonRuntimeVerificationReceiptStatement.model_fields
    )
    forbidden = {
        "writer_exclusion_lease_ref",
        "immutable_snapshot_ref",
        "continuous_immutability",
        "runtime_subtree_cutoff_ref",
    }
    assert fields.isdisjoint(forbidden)


def _c1_signed_binding(
    record: authority_module.FoundryRecordRef[DigestDomain],
    *,
    role: TrustRole,
    evidence_label: str,
) -> authority_module.PersistedSignedFoundryRecordBinding[DigestDomain]:
    if role is TrustRole.FOUNDRY_TRUST_ROOT:
        basis: authority_module.SignedRecordVerificationBasis = (
            authority_module.evidence_module.SourceAuthorityVerificationBasis(
                kind="source_authority",
                source_authority_ref=_c1_ref(DigestDomain.CANONICAL_SOURCE, "source"),
            )
        )
    else:
        basis = authority_module.evidence_module.ResolvedTrustVerificationBasis(
            kind="resolved_trust",
            trust_resolution_receipt_ref=_c1_ref(
                DigestDomain.TRUST_RESOLUTION,
                f"trust:{role.value}",
            ),
        )
    evidence = authority_module.ExactSignedArtifactEvidenceStatement(
        schema_version="polisyos.foundry.signed-artifact-evidence.v1",
        signed_blob_bytes=evidence_label.encode(),
        exact_manifest_bytes=f"manifest:{evidence_label}".encode(),
        detached_signature_bytes=f"signature:{evidence_label}".encode(),
    )
    evidence_ref = record_ref(
        DigestDomain.SIGNED_EVIDENCE,
        canonical_json_bytes(evidence.model_dump(mode="json")),
        schema_version=evidence.schema_version,
    )
    statement = authority_module.SignedFoundryRecordBindingStatement[DigestDomain](
        schema_version="polisyos.foundry.signed-record-binding.v1",
        record_ref=record,
        signed_evidence_ref=evidence_ref,
        required_role=role,
        verification_basis=basis,
        verifier_provenance_ref=_c1_ref(
            DigestDomain.VERIFIER_PROVENANCE,
            f"verifier:{role.value}",
        ),
    )
    return authority_module.PersistedSignedFoundryRecordBinding[DigestDomain](
        binding_ref=authority_module.build_foundry_statement_ref(
            DigestDomain.SIGNED_RECORD_BINDING,
            statement,
        ),
        statement=statement,
    )


def _put_c1_statement(
    store: FileSystemCAS,
    domain: DigestDomain,
    statement: FoundryAuthorityModel,
) -> authority_module.FoundryRecordRef[DigestDomain]:
    raw = canonical_json_bytes(statement.model_dump(mode="json"))
    expected = authority_module.build_foundry_statement_ref(domain, statement)
    stored = store.put_bytes(
        raw,
        PutOptions(
            kind=f"test.gy_n12.{domain.value}",
            media_type="application/json",
        ),
    )
    assert str(stored.artifact_id) == expected.artifact_id
    return expected


@dataclass(frozen=True, slots=True)
class _C1TransportCapsule:
    store_root: Path
    capsule_path: Path
    capsule: authority_module.PersistedFoundryDependencyAuthorityCapsule
    index: authority_module.PersistedSignedRecordBindingIndex
    bindings: tuple[
        authority_module.PersistedSignedFoundryRecordBinding[DigestDomain], ...
    ]


def _c1_transport_binding(
    statement: FoundryAuthorityModel,
    *,
    domain: DigestDomain,
    role: TrustRole,
    source_ref: authority_module.FoundryRecordRef[
        Literal[DigestDomain.CANONICAL_SOURCE]
    ],
) -> tuple[
    authority_module.PersistedSignedFoundryRecordBinding[DigestDomain],
    authority_module.ExactSignedArtifactEvidenceStatement,
]:
    record_raw = canonical_json_bytes(statement.model_dump(mode="json"))
    record = authority_module.build_foundry_statement_ref(domain, statement)
    evidence = authority_module.ExactSignedArtifactEvidenceStatement(
        schema_version="polisyos.foundry.signed-artifact-evidence.v1",
        signed_blob_bytes=record_raw,
        exact_manifest_bytes=f"manifest:{domain.value}".encode(),
        detached_signature_bytes=f"signature:{domain.value}".encode(),
    )
    evidence_ref = authority_module.build_foundry_statement_ref(
        DigestDomain.SIGNED_EVIDENCE,
        evidence,
    )
    if role is TrustRole.FOUNDRY_TRUST_ROOT:
        basis: authority_module.SignedRecordVerificationBasis = (
            authority_module.evidence_module.SourceAuthorityVerificationBasis(
                kind="source_authority",
                source_authority_ref=source_ref,
            )
        )
    else:
        basis = authority_module.evidence_module.ResolvedTrustVerificationBasis(
            kind="resolved_trust",
            trust_resolution_receipt_ref=_c1_ref(
                DigestDomain.TRUST_RESOLUTION,
                f"trust:{role.value}",
            ),
        )
    binding_statement = authority_module.SignedFoundryRecordBindingStatement[
        DigestDomain
    ](
        schema_version="polisyos.foundry.signed-record-binding.v1",
        record_ref=record,
        signed_evidence_ref=evidence_ref,
        required_role=role,
        verification_basis=basis,
        verifier_provenance_ref=_c1_ref(
            DigestDomain.VERIFIER_PROVENANCE,
            f"verifier:{role.value}",
        ),
    )
    return (
        authority_module.PersistedSignedFoundryRecordBinding[DigestDomain](
            binding_ref=authority_module.build_foundry_statement_ref(
                DigestDomain.SIGNED_RECORD_BINDING,
                binding_statement,
            ),
            statement=binding_statement,
        ),
        evidence,
    )


def _write_c1_transport_capsule(tmp_path: Path) -> _C1TransportCapsule:
    store_root = tmp_path / "cas"
    store = FileSystemCAS(store_root)
    source_ref = _c1_ref(DigestDomain.CANONICAL_SOURCE, "transport-source")
    appointment, custody = _c1_appointment_pair(
        root_label="transport-root",
        custodian_label="transport-custodian",
        manifest_label="transport-manifest",
    )
    build = authority_module.evidence_module.BuildLineageStatement(
        schema_version="polisyos.foundry.build-lineage.v1",
        source_artifact_ref=_c1_ref(DigestDomain.SELECTED_SOURCE, "build-source"),
        builder_toolchain_ref=_c1_ref(
            DigestDomain.TOOLCHAIN_RUNTIME,
            "build-runtime",
        ),
        build_profile_ref=_c1_ref(DigestDomain.BUILD_PROFILE, "build-profile"),
        normalized_argv_hash=domain_digest(DigestDomain.BUILD_ARGV, b"build-argv"),
        build_environment_hash=domain_digest(
            DigestDomain.BUILD_ENVIRONMENT,
            b"build-environment",
        ),
        output_wheel_ref=_c1_ref(DigestDomain.SELECTED_WHEEL, "build-wheel"),
        verifier_provenance_ref=_c1_ref(
            DigestDomain.VERIFIER_PROVENANCE,
            "build-verifier",
        ),
        trust_resolution_receipt_ref=_c1_ref(
            DigestDomain.TRUST_RESOLUTION,
            "build-trust",
        ),
    )
    key_bytes = bytes(range(32))
    trust = _c1_trust_material(
        TrustPublicKey(
            key_id="sha256:" + hashlib.sha256(key_bytes).hexdigest(),
            algorithm="ed25519",
            public_key_encoding="raw-ed25519-32",
            public_key_bytes=key_bytes,
            signer_identity="transport-root",
            roles=(TrustRole.FOUNDRY_TRUST_ROOT,),
        )
    )
    statements = (
        (DigestDomain.PRODUCTION_APPOINTMENT, appointment, TrustRole.APPOINTMENT_ISSUER),
        (DigestDomain.PRODUCTION_CUSTODY, custody, TrustRole.CUSTODY_VERIFIER),
        (DigestDomain.BUILD_LINEAGE, build, TrustRole.BUILD_VERIFIER),
        (DigestDomain.TRUST_MATERIAL, trust, TrustRole.FOUNDRY_TRUST_ROOT),
    )
    bound = tuple(
        _c1_transport_binding(
            statement,
            domain=domain,
            role=role,
            source_ref=source_ref,
        )
        for domain, statement, role in statements
    )
    bindings = tuple(sorted((row[0] for row in bound), key=lambda row: row.binding_ref.artifact_id))
    index_statement = authority_module.evidence_module.SignedRecordBindingIndexStatement(
        schema_version="polisyos.foundry.signed-binding-index.v1",
        source_authority_ref=source_ref,
        binding_refs=tuple(row.binding_ref for row in bindings),
    )
    index = authority_module.PersistedSignedRecordBindingIndex(
        index_ref=authority_module.build_foundry_statement_ref(
            DigestDomain.SIGNED_BINDING_INDEX,
            index_statement,
        ),
        statement=index_statement,
    )
    refs = {domain: authority_module.build_foundry_statement_ref(domain, statement) for domain, statement, _role in statements}
    capsule_statement = authority_module.FoundryDependencyAuthorityCapsuleStatement(
        schema_version="polisyos.foundry.dependency-capsule.v1",
        source_authority_ref=source_ref,
        profile_admission_ref=_c1_ref(DigestDomain.PROFILE_ADMISSION, "transport-admission"),
        appointment_ref=refs[DigestDomain.PRODUCTION_APPOINTMENT],
        signed_binding_index_ref=index.index_ref,
        environment_receipt_ref=_c1_ref(
            DigestDomain.ENVIRONMENT_RECEIPT,
            "transport-environment",
        ),
        selected_artifact_refs=(),
        build_lineage_refs=(refs[DigestDomain.BUILD_LINEAGE],),
        trust_material_refs=(refs[DigestDomain.TRUST_MATERIAL],),
    )
    capsule = authority_module.PersistedFoundryDependencyAuthorityCapsule(
        capsule_ref=authority_module.build_foundry_statement_ref(
            DigestDomain.CAPSULE,
            capsule_statement,
        ),
        statement=capsule_statement,
    )
    _put_c1_statement(store, DigestDomain.SIGNED_BINDING_INDEX, index.statement)
    for domain, statement, _role in statements:
        _put_c1_statement(store, domain, statement)
    evidence_by_ref = {row[0].statement.signed_evidence_ref: row[1] for row in bound}
    for binding in bindings:
        _put_c1_statement(store, DigestDomain.SIGNED_RECORD_BINDING, binding.statement)
        _put_c1_statement(
            store,
            DigestDomain.SIGNED_EVIDENCE,
            evidence_by_ref[binding.statement.signed_evidence_ref],
        )
    capsule_path = (
        tmp_path
        / "environment"
        / ".polisyos-foundry-authority-v1"
        / "dependency-authority-capsule.json"
    )
    capsule_path.parent.mkdir(parents=True)
    capsule_path.write_bytes(canonical_json_bytes(capsule.model_dump(mode="json")))
    return _C1TransportCapsule(
        store_root=store_root,
        capsule_path=capsule_path,
        capsule=capsule,
        index=index,
        bindings=bindings,
    )


def _run_fresh_capsule_probe(
    fixture: _C1TransportCapsule,
    *,
    include_bindings: bool,
    tmp_path: Path,
) -> dict[str, object]:
    probe = r"""
import json
import sys
from pathlib import Path
from polisyos.core.artifacts import FileSystemCAS
from polisyos.foundry.methods.catalog import dependency_authority as authority

store = FileSystemCAS(Path(sys.argv[1]))
port = authority.FileSystemCASFoundryBootstrapEvidencePort(
    store=store,
    capsule_index_path=Path(sys.argv[2]),
)
capsule = port.load_capsule_raw()
index = port.load_binding_index_raw(index_ref=capsule.statement.signed_binding_index_ref)
rows = []
if sys.argv[3] == "bindings":
    for binding_ref in index.statement.binding_refs:
        binding = port.load_binding_raw(binding_ref=binding_ref)
        evidence = port.load_exact_evidence_raw(
            evidence_ref=binding.statement.signed_evidence_ref
        )
        record_raw = store.get_bytes(authority._strict_artifact_id(binding.statement.record_ref))
        statement = authority.load_strict_foundry_statement(
            record=binding.statement.record_ref,
            raw=record_raw,
        )
        rows.append({
            "domain": binding.statement.record_ref.semantic_hash.domain.value,
            "role": binding.statement.required_role.value,
            "basis": binding.statement.verification_basis.kind,
            "schema": statement.schema_version,
            "signed_blob_matches": evidence.signed_blob_bytes == record_raw,
        })
print(json.dumps({
    "capsule_ref": capsule.capsule_ref.artifact_id,
    "index_ref": index.index_ref.artifact_id,
    "rows": rows,
}, sort_keys=True))
"""
    fresh_cwd = tmp_path / "fresh-cwd"
    fresh_cwd.mkdir()
    env = {
        key: value
        for key, value in os.environ.items()
        if not any(token in key for token in ("CAS", "SIGNING", "PRIVATE_KEY"))
    }
    completed = subprocess.run(
        [
            str(_PRODUCT_ROOT / ".venv" / "bin" / "python"),
            "-c",
            probe,
            str(fixture.store_root),
            str(fixture.capsule_path),
            "bindings" if include_bindings else "capsule",
        ],
        cwd=fresh_cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_fresh_n8_process_reopens_exact_environment_authority_capsule(
    tmp_path: Path,
) -> None:
    fixture = _write_c1_transport_capsule(tmp_path)

    observed = _run_fresh_capsule_probe(
        fixture,
        include_bindings=False,
        tmp_path=tmp_path,
    )

    assert observed == {
        "capsule_ref": fixture.capsule.capsule_ref.artifact_id,
        "index_ref": fixture.index.index_ref.artifact_id,
        "rows": [],
    }
    tampered = fixture.capsule.model_copy(
        update={"capsule_ref": _c1_ref(DigestDomain.CAPSULE, "wrong-capsule")}
    )
    fixture.capsule_path.write_bytes(
        canonical_json_bytes(tampered.model_dump(mode="json"))
    )
    port = authority_module.FileSystemCASFoundryBootstrapEvidencePort(
        store=FileSystemCAS(fixture.store_root),
        capsule_index_path=fixture.capsule_path,
    )
    with pytest.raises(ValueError, match="capsule.*content-bound"):
        port.load_capsule_raw()


def test_fresh_process_reopens_appointment_custody_trust_and_lineage_bindings(
    tmp_path: Path,
) -> None:
    fixture = _write_c1_transport_capsule(tmp_path)

    observed = _run_fresh_capsule_probe(
        fixture,
        include_bindings=True,
        tmp_path=tmp_path,
    )

    rows = observed["rows"]
    assert isinstance(rows, list)
    assert {
        (row["domain"], row["role"], row["basis"])
        for row in rows
        if isinstance(row, dict)
    } == {
        ("production-data-appointment", "appointment_issuer", "resolved_trust"),
        ("production-data-custody", "custody_verifier", "resolved_trust"),
        ("build-lineage-receipt", "build_verifier", "resolved_trust"),
        ("trust-material", "foundry_trust_root", "source_authority"),
    }
    assert all(
        row["signed_blob_matches"] is True
        for row in rows
        if isinstance(row, dict)
    )


class _FixtureTrustResolver:
    def __init__(
        self,
        *,
        policy_ref: authority_module.FoundryRecordRef[
            Literal[DigestDomain.TRUST_POLICY]
        ],
        entries: dict[
            TrustRole,
            tuple[
                authority_module.PersistedTrustResolutionReceipt,
                Ed25519Verifier,
            ],
        ],
    ) -> None:
        self._policy_ref = policy_ref
        self._entries = entries

    def resolve(
        self,
        *,
        policy_ref: authority_module.FoundryRecordRef[
            Literal[DigestDomain.TRUST_POLICY]
        ],
        required_role: TrustRole,
    ) -> object:
        if policy_ref != self._policy_ref or required_role not in self._entries:
            raise ValueError("fixture trust request is outside its appointed denominator")
        receipt, verifier = self._entries[required_role]
        return authority_module._mint_owner_capability(
            authority_module._RESOLVED_TRUST_SPEC,
            authority_module._ResolvedFoundryTrustPayload(
                receipt=receipt,
                verifier=verifier,
            ),
        )


@dataclass(frozen=True, slots=True)
class _C1SignedRepositoryFixture:
    store: FileSystemCAS
    source: authority_module.CanonicalFoundrySourceAuthority
    source_ref: authority_module.FoundryRecordRef[
        Literal[DigestDomain.CANONICAL_SOURCE]
    ]
    repository: authority_module.FileSystemCASSignedRecordRepository
    receipts: dict[TrustRole, authority_module.PersistedTrustResolutionReceipt]
    signers: dict[TrustRole, Ed25519Signer]
    signer_identities: dict[TrustRole, str]


def _c1_signed_repository_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    roles: tuple[TrustRole, ...],
) -> _C1SignedRepositoryFixture:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path / "source-fixture",
    )
    source = authority_module._build_production_canonical_source_resolver().resolve(
        request=_authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(source, authority_module.CanonicalFoundrySourceAuthority)
    with authority_module._unwrap_owner_capability(
        source,
        authority_module._CANONICAL_SOURCE_SPEC,
    ) as source_payload:
        source_ref = source_payload.authority_ref
        source_cutoff = source_payload.statement.source_freeze_commit
    store = FileSystemCAS(tmp_path / "signed-cas")
    policy_ref = _c1_ref(DigestDomain.TRUST_POLICY, "fixture-policy")
    entries: dict[
        TrustRole,
        tuple[authority_module.PersistedTrustResolutionReceipt, Ed25519Verifier],
    ] = {}
    signers: dict[TrustRole, Ed25519Signer] = {}
    identities: dict[TrustRole, str] = {}
    receipts: dict[TrustRole, authority_module.PersistedTrustResolutionReceipt] = {}
    for role in roles:
        pair = KeyPair.generate()
        identity = f"fixture:{role.value}"
        signer = Ed25519Signer(pair.private_key)
        verifier = Ed25519Verifier(strict_identity=True)
        verifier.add_trusted_key(
            pair.public_key,
            key_id=pair.key_id,
            identity=identity,
        )
        receipt_statement = authority_module.evidence_module.TrustResolutionReceiptStatement(
            schema_version="polisyos.foundry.trust-resolution.v1",
            source_authority_ref=source_ref,
            source_freeze_commit=source_cutoff,
            trust_policy_ref=policy_ref,
            required_role=role,
            trust_material_ref=_c1_ref(
                DigestDomain.TRUST_MATERIAL,
                f"fixture-material:{role.value}",
            ),
            eligible_keys=(
                authority_module.evidence_module.ResolvedTrustKey(
                    key_id=pair.key_id,
                    signer_identity=identity,
                    selected_role=role,
                ),
            ),
            revocation_dispositions=(),
            verifier_provenance_ref=_c1_ref(
                DigestDomain.VERIFIER_PROVENANCE,
                f"fixture-verifier:{role.value}",
            ),
        )
        receipt = authority_module.PersistedTrustResolutionReceipt(
            receipt_ref=authority_module.build_foundry_statement_ref(
                DigestDomain.TRUST_RESOLUTION,
                receipt_statement,
            ),
            statement=receipt_statement,
        )
        _put_c1_statement(store, DigestDomain.TRUST_RESOLUTION, receipt_statement)
        entries[role] = (receipt, verifier)
        receipts[role] = receipt
        signers[role] = signer
        identities[role] = identity
    resolver = _FixtureTrustResolver(policy_ref=policy_ref, entries=entries)
    return _C1SignedRepositoryFixture(
        store=store,
        source=source,
        source_ref=source_ref,
        repository=authority_module.FileSystemCASSignedRecordRepository(
            store=store,
            trust_resolver=resolver,
        ),
        receipts=receipts,
        signers=signers,
        signer_identities=identities,
    )


def _persist_real_signed_record(
    fixture: _C1SignedRepositoryFixture,
    *,
    domain: DigestDomain,
    statement: FoundryAuthorityModel,
    role: TrustRole,
    signer: Ed25519Signer | None = None,
    signer_identity: str | None = None,
    verifier_provenance_ref: authority_module.FoundryRecordRef[
        Literal[DigestDomain.VERIFIER_PROVENANCE]
    ]
    | None = None,
) -> authority_module.PersistedSignedFoundryRecordBinding[DigestDomain]:
    record_raw = canonical_json_bytes(statement.model_dump(mode="json"))
    record_ref_value = _put_c1_statement(fixture.store, domain, statement)
    record_id = authority_module._strict_artifact_id(record_ref_value)
    manifest_raw = fixture.store.get_manifest_bytes(record_id)
    selected_signer = signer or fixture.signers[role]
    signature = selected_signer.sign(
        record_id,
        record_raw,
        manifest_raw,
        signer_identity=signer_identity or fixture.signer_identities[role],
    )
    evidence = authority_module.ExactSignedArtifactEvidenceStatement(
        schema_version="polisyos.foundry.signed-artifact-evidence.v1",
        signed_blob_bytes=record_raw,
        exact_manifest_bytes=manifest_raw,
        detached_signature_bytes=canonical_json_bytes(
            signature.model_dump(mode="json")
        ),
    )
    evidence_ref = _put_c1_statement(
        fixture.store,
        DigestDomain.SIGNED_EVIDENCE,
        evidence,
    )
    receipt = fixture.receipts[role]
    binding_statement = authority_module.SignedFoundryRecordBindingStatement[
        DigestDomain
    ](
        schema_version="polisyos.foundry.signed-record-binding.v1",
        record_ref=record_ref_value,
        signed_evidence_ref=evidence_ref,
        required_role=role,
        verification_basis=authority_module.evidence_module.ResolvedTrustVerificationBasis(
            kind="resolved_trust",
            trust_resolution_receipt_ref=receipt.receipt_ref,
        ),
        verifier_provenance_ref=verifier_provenance_ref
        or receipt.statement.verifier_provenance_ref,
    )
    binding_ref = _put_c1_statement(
        fixture.store,
        DigestDomain.SIGNED_RECORD_BINDING,
        binding_statement,
    )
    return authority_module.PersistedSignedFoundryRecordBinding[DigestDomain](
        binding_ref=cast(
            "authority_module.FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]]",
            binding_ref,
        ),
        statement=binding_statement,
    )


def test_random_signature_custody_and_verifier_refs_fail_after_resolution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture = _c1_signed_repository_fixture(
        monkeypatch,
        tmp_path,
        roles=(TrustRole.APPOINTMENT_ISSUER, TrustRole.CUSTODY_VERIFIER),
    )
    appointment, custody = _c1_appointment_pair(
        root_label="signed-root",
        custodian_label="signed-custodian",
        manifest_label="signed-manifest",
    )
    random_pair = KeyPair.generate()
    random_signature = _persist_real_signed_record(
        fixture,
        domain=DigestDomain.PRODUCTION_APPOINTMENT,
        statement=appointment,
        role=TrustRole.APPOINTMENT_ISSUER,
        signer=Ed25519Signer(random_pair.private_key),
        signer_identity="unappointed-random-signer",
    )
    random_result = fixture.repository.load_and_verify_binding(
        binding_ref=random_signature.binding_ref,
        expected_record_domain=DigestDomain.PRODUCTION_APPOINTMENT,
        source_authority=fixture.source,
    )
    assert isinstance(random_result, RejectedAuthorityPredicate)
    assert random_result.failure_code is AuthorityFailureCode.SIGNATURE_INVALID

    substituted_verifier = _persist_real_signed_record(
        fixture,
        domain=DigestDomain.PRODUCTION_CUSTODY,
        statement=custody,
        role=TrustRole.CUSTODY_VERIFIER,
        verifier_provenance_ref=_c1_ref(
            DigestDomain.VERIFIER_PROVENANCE,
            "substituted-verifier",
        ),
    )
    verifier_result = fixture.repository.load_and_verify_binding(
        binding_ref=substituted_verifier.binding_ref,
        expected_record_domain=DigestDomain.PRODUCTION_CUSTODY,
        source_authority=fixture.source,
    )
    assert isinstance(verifier_result, RejectedAuthorityPredicate)
    assert verifier_result.failure_code is AuthorityFailureCode.SIGNATURE_INVALID

    wrong_appointment = appointment.model_copy(
        update={
            "custody_statement_ref": _c1_ref(
                DigestDomain.PRODUCTION_CUSTODY,
                "different-authentic-custody",
            )
        }
    )
    appointment_binding = _persist_real_signed_record(
        fixture,
        domain=DigestDomain.PRODUCTION_APPOINTMENT,
        statement=wrong_appointment,
        role=TrustRole.APPOINTMENT_ISSUER,
    )
    custody_binding = _persist_real_signed_record(
        fixture,
        domain=DigestDomain.PRODUCTION_CUSTODY,
        statement=custody,
        role=TrustRole.CUSTODY_VERIFIER,
    )
    tokens: list[object] = []
    graph: object | None = None
    try:
        for binding, domain in (
            (appointment_binding, DigestDomain.PRODUCTION_APPOINTMENT),
            (custody_binding, DigestDomain.PRODUCTION_CUSTODY),
        ):
            verified = fixture.repository.load_and_verify_binding(
                binding_ref=binding.binding_ref,
                expected_record_domain=domain,
                source_authority=fixture.source,
            )
            assert isinstance(verified, authority_module.VerifiedSignedFoundryRecord)
            tokens.append(verified)
        graph = _mint_test_signed_graph(
            tuple(
                (domain, token, binding.binding_ref)
                for token, (binding, domain) in zip(
                    tokens,
                    (
                        (appointment_binding, DigestDomain.PRODUCTION_APPOINTMENT),
                        (custody_binding, DigestDomain.PRODUCTION_CUSTODY),
                    ),
                    strict=True,
                )
            )
        )
        with authority_module._unwrap_owner_capability(
            graph,
            authority_module._SIGNED_GRAPH_SPEC,
        ) as graph_payload:
            capsule_statement = authority_module.FoundryDependencyAuthorityCapsuleStatement(
                schema_version="polisyos.foundry.dependency-capsule.v1",
                source_authority_ref=fixture.source_ref,
                profile_admission_ref=_c1_ref(
                    DigestDomain.PROFILE_ADMISSION,
                    "signed-admission",
                ),
                appointment_ref=appointment_binding.statement.record_ref,
                signed_binding_index_ref=graph_payload.index.index_ref,
                environment_receipt_ref=_c1_ref(
                    DigestDomain.ENVIRONMENT_RECEIPT,
                    "signed-environment",
                ),
                selected_artifact_refs=(),
                build_lineage_refs=(),
                trust_material_refs=(),
            )
        capsule = authority_module.PersistedFoundryDependencyAuthorityCapsule(
            capsule_ref=authority_module.build_foundry_statement_ref(
                DigestDomain.CAPSULE,
                capsule_statement,
            ),
            statement=capsule_statement,
        )
        with authority_module._unwrap_owner_capability(
            fixture.source,
            authority_module._CANONICAL_SOURCE_SPEC,
        ) as source_payload:
            appointment_authority = authority_module._ProductionDataAppointmentAuthority(
                source_authority=source_payload
            )
        custody_result = appointment_authority.resolve(
            source_authority=fixture.source,
            capsule=capsule,
            signed_graph=graph,
        )
        assert isinstance(custody_result, RejectedAuthorityPredicate)
        assert custody_result.failure_code is AuthorityFailureCode.APPOINTMENT_MISMATCH
    finally:
        if graph is not None:
            authority_module._release_owner_capability(
                graph,
                authority_module._SIGNED_GRAPH_SPEC,
            )
        for token in tokens:
            authority_module._release_owner_capability(
                token,
                authority_module._SIGNED_RECORD_SPEC,
            )
        authority_module._release_owner_capability(
            fixture.source,
            authority_module._CANONICAL_SOURCE_SPEC,
        )


def test_canonical_store_blob_manifest_or_signature_corruption_fails_before_parse(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture = _c1_signed_repository_fixture(
        monkeypatch,
        tmp_path,
        roles=(TrustRole.CUSTODY_VERIFIER,),
    )
    _appointment, custody = _c1_appointment_pair(
        root_label="corruption-root",
        custodian_label="corruption-custodian",
        manifest_label="corruption-manifest",
    )
    clean_binding = _persist_real_signed_record(
        fixture,
        domain=DigestDomain.PRODUCTION_CUSTODY,
        statement=custody,
        role=TrustRole.CUSTODY_VERIFIER,
    )
    original_parser = authority_module.load_strict_foundry_statement
    target_parse_calls = 0

    def parsing_spy(
        *,
        record: authority_module.FoundryRecordRef[DigestDomain],
        raw: bytes,
    ) -> FoundryAuthorityModel:
        nonlocal target_parse_calls
        if record.semantic_hash.domain is DigestDomain.PRODUCTION_CUSTODY:
            target_parse_calls += 1
        return original_parser(record=record, raw=raw)

    monkeypatch.setattr(authority_module, "load_strict_foundry_statement", parsing_spy)
    record_id = authority_module._strict_artifact_id(clean_binding.statement.record_ref)
    blob_path, manifest_path = fixture.store.get_paths(record_id)
    blob_raw = blob_path.read_bytes()
    manifest_raw = manifest_path.read_bytes()
    try:
        for target, original, corrupted in (
            (blob_path, blob_raw, b"X" * len(blob_raw)),
            (manifest_path, manifest_raw, b'{"corrupt":true}'),
        ):
            target.write_bytes(corrupted)
            target_parse_calls = 0
            result = fixture.repository.load_and_verify_binding(
                binding_ref=clean_binding.binding_ref,
                expected_record_domain=DigestDomain.PRODUCTION_CUSTODY,
                source_authority=fixture.source,
            )
            assert isinstance(result, RejectedAuthorityPredicate)
            assert result.failure_code is AuthorityFailureCode.SIGNATURE_INVALID
            assert target_parse_calls == 0
            target.write_bytes(original)

        random_pair = KeyPair.generate()
        invalid_signature = _persist_real_signed_record(
            fixture,
            domain=DigestDomain.PRODUCTION_CUSTODY,
            statement=custody,
            role=TrustRole.CUSTODY_VERIFIER,
            signer=Ed25519Signer(random_pair.private_key),
            signer_identity="unappointed-corruption-signer",
        )
        target_parse_calls = 0
        invalid_result = fixture.repository.load_and_verify_binding(
            binding_ref=invalid_signature.binding_ref,
            expected_record_domain=DigestDomain.PRODUCTION_CUSTODY,
            source_authority=fixture.source,
        )
        assert isinstance(invalid_result, RejectedAuthorityPredicate)
        assert invalid_result.failure_code is AuthorityFailureCode.SIGNATURE_INVALID
        assert target_parse_calls == 0

        target_parse_calls = 0
        clean_result = fixture.repository.load_and_verify_binding(
            binding_ref=clean_binding.binding_ref,
            expected_record_domain=DigestDomain.PRODUCTION_CUSTODY,
            source_authority=fixture.source,
        )
        assert isinstance(clean_result, authority_module.VerifiedSignedFoundryRecord)
        assert target_parse_calls == 1
        authority_module._release_owner_capability(
            clean_result,
            authority_module._SIGNED_RECORD_SPEC,
        )
    finally:
        blob_path.write_bytes(blob_raw)
        manifest_path.write_bytes(manifest_raw)
        authority_module._release_owner_capability(
            fixture.source,
            authority_module._CANONICAL_SOURCE_SPEC,
        )


def test_source_a_bootstrap_cannot_resolve_source_b_or_another_cutoff() -> None:
    source_a = _c1_ref(DigestDomain.CANONICAL_SOURCE, "source-a")
    snapshot = authority_module.FoundryTrustBootstrapSnapshot(
        source_authority_ref=source_a,
        source_freeze_commit="1" * 40,
        binding_index_ref=_c1_ref(DigestDomain.SIGNED_BINDING_INDEX, "index"),
        trust_materials=(
            authority_module.evidence_module.PersistedTrustMaterial(
                material_ref=_c1_ref(DigestDomain.TRUST_MATERIAL, "material"),
                statement=_c1_trust_material(
                    TrustPublicKey(
                        key_id="sha256:" + hashlib.sha256(b"a" * 32).hexdigest(),
                        algorithm="ed25519",
                        public_key_encoding="raw-ed25519-32",
                        public_key_bytes=b"a" * 32,
                        signer_identity="root-a",
                        roles=(TrustRole.FOUNDRY_TRUST_ROOT,),
                    )
                ),
                signed_binding_ref=_c1_ref(
                    DigestDomain.SIGNED_RECORD_BINDING,
                    "material-binding",
                ),
            ),
        ),
        revocations=(),
    )
    authority_module.validate_trust_bootstrap_basis(
        snapshot,
        expected_source_ref=source_a,
        expected_cutoff="1" * 40,
    )
    for source_ref, cutoff in (
        (_c1_ref(DigestDomain.CANONICAL_SOURCE, "source-b"), "1" * 40),
        (source_a, "2" * 40),
    ):
        with pytest.raises(ValueError, match="trust bootstrap basis"):
            authority_module.validate_trust_bootstrap_basis(
                snapshot,
                expected_source_ref=source_ref,
                expected_cutoff=cutoff,
            )


def test_source_trust_bootstrap_precedes_role_resolver_without_repository_cycle() -> None:
    source = inspect.getsource(authority_module._build_sealed_foundry_trust_resolver)
    assert "_VerifiedFoundryTrustBootstrapPayload" in source
    assert "GitCommitAncestryAuthority" in source
    assert "CanonicalSignedRecordRepository" not in source
    bootstrap_source = inspect.getsource(
        authority_module._ProductionFoundrySourceTrustBootstrapper.bootstrap
    )
    assert "_ProductionFoundryTrustResolver" not in bootstrap_source


def test_trust_receipt_changes_with_policy_cutoff_or_role() -> None:
    key_bytes = b"r" * 32
    key = TrustPublicKey(
        key_id="sha256:" + hashlib.sha256(key_bytes).hexdigest(),
        algorithm="ed25519",
        public_key_encoding="raw-ed25519-32",
        public_key_bytes=key_bytes,
        signer_identity="root",
        roles=(TrustRole.APPOINTMENT_ISSUER, TrustRole.CUSTODY_VERIFIER),
    )
    material = _c1_trust_material(key)
    material_ref = record_ref(
        DigestDomain.TRUST_MATERIAL,
        canonical_json_bytes(material.model_dump(mode="json")),
        schema_version=material.schema_version,
    )

    def receipt(*, cutoff: str, role: TrustRole, policy: str) -> object:
        statement = authority_module.evidence_module.TrustResolutionReceiptStatement(
            schema_version="polisyos.foundry.trust-resolution.v1",
            source_authority_ref=_c1_ref(DigestDomain.CANONICAL_SOURCE, "source"),
            source_freeze_commit=cutoff,
            trust_policy_ref=_c1_ref(DigestDomain.TRUST_POLICY, policy),
            required_role=role,
            trust_material_ref=material_ref,
            eligible_keys=(
                authority_module.evidence_module.ResolvedTrustKey(
                    key_id=key.key_id,
                    signer_identity=key.signer_identity,
                    selected_role=role,
                ),
            ),
            revocation_dispositions=(),
            verifier_provenance_ref=_c1_ref(
                DigestDomain.VERIFIER_PROVENANCE,
                "verifier",
            ),
        )
        return record_ref(
            DigestDomain.TRUST_RESOLUTION,
            canonical_json_bytes(statement.model_dump(mode="json")),
            schema_version=statement.schema_version,
        )

    baseline = receipt(
        cutoff="1" * 40,
        role=TrustRole.APPOINTMENT_ISSUER,
        policy="policy-a",
    )
    assert baseline != receipt(
        cutoff="2" * 40,
        role=TrustRole.APPOINTMENT_ISSUER,
        policy="policy-a",
    )
    assert baseline != receipt(
        cutoff="1" * 40,
        role=TrustRole.CUSTODY_VERIFIER,
        policy="policy-a",
    )
    assert baseline != receipt(
        cutoff="1" * 40,
        role=TrustRole.APPOINTMENT_ISSUER,
        policy="policy-b",
    )


def _c1_capsule_graph() -> tuple[
    authority_module.PersistedFoundryDependencyAuthorityCapsule,
    authority_module.PersistedSignedRecordBindingIndex,
    tuple[authority_module.PersistedSignedFoundryRecordBinding[DigestDomain], ...],
]:
    appointment_ref = _c1_ref(DigestDomain.PRODUCTION_APPOINTMENT, "appointment")
    build_ref = _c1_ref(DigestDomain.BUILD_LINEAGE, "build")
    trust_ref = _c1_ref(DigestDomain.TRUST_MATERIAL, "trust")
    bindings = tuple(
        sorted(
            (
                _c1_signed_binding(
                    appointment_ref,
                    role=TrustRole.APPOINTMENT_ISSUER,
                    evidence_label="appointment",
                ),
                _c1_signed_binding(
                    build_ref,
                    role=TrustRole.BUILD_VERIFIER,
                    evidence_label="build",
                ),
                _c1_signed_binding(
                    trust_ref,
                    role=TrustRole.FOUNDRY_TRUST_ROOT,
                    evidence_label="trust",
                ),
            ),
            key=lambda row: row.binding_ref.artifact_id,
        )
    )
    source_ref = _c1_ref(DigestDomain.CANONICAL_SOURCE, "source")
    index_statement = authority_module.evidence_module.SignedRecordBindingIndexStatement(
        schema_version="polisyos.foundry.signed-binding-index.v1",
        source_authority_ref=source_ref,
        binding_refs=tuple(row.binding_ref for row in bindings),
    )
    index = authority_module.PersistedSignedRecordBindingIndex(
        index_ref=authority_module.build_foundry_statement_ref(
            DigestDomain.SIGNED_BINDING_INDEX,
            index_statement,
        ),
        statement=index_statement,
    )
    capsule_statement = authority_module.FoundryDependencyAuthorityCapsuleStatement(
        schema_version="polisyos.foundry.dependency-capsule.v1",
        source_authority_ref=source_ref,
        profile_admission_ref=_c1_ref(DigestDomain.PROFILE_ADMISSION, "admission"),
        appointment_ref=appointment_ref,
        signed_binding_index_ref=index.index_ref,
        environment_receipt_ref=_c1_ref(
            DigestDomain.ENVIRONMENT_RECEIPT,
            "environment",
        ),
        selected_artifact_refs=(),
        build_lineage_refs=(build_ref,),
        trust_material_refs=(trust_ref,),
    )
    capsule = authority_module.PersistedFoundryDependencyAuthorityCapsule(
        capsule_ref=record_ref(
            DigestDomain.CAPSULE,
            canonical_json_bytes(capsule_statement.model_dump(mode="json")),
            schema_version=capsule_statement.schema_version,
        ),
        statement=capsule_statement,
    )
    return capsule, index, bindings


def test_capsule_signed_binding_index_is_exact_graph_bijection() -> None:
    capsule, index, bindings = _c1_capsule_graph()
    registry = decode_digest_domain_registry_toml(_DIGEST_REGISTRY.read_bytes())
    infrastructure = {
        DigestDomain.CAPSULE,
        DigestDomain.SIGNED_EVIDENCE,
        DigestDomain.SIGNED_RECORD_BINDING,
        DigestDomain.SIGNED_BINDING_INDEX,
    }
    rows = {row.domain_id: row for row in registry.statement.domains}
    assert {
        domain: rows[domain].signature_requirement for domain in infrastructure
    } == dict.fromkeys(infrastructure, "unsigned")
    authority_module.validate_capsule_signed_binding_index(
        capsule,
        index,
        bindings,
        digest_registry=registry,
    )
    for domain in infrastructure:
        changed_rows = tuple(
            row.model_copy(
                update={
                    "signature_requirement": "signed",
                    "required_signer_role": TrustRole.FOUNDRY_TRUST_ROOT,
                }
            )
            if row.domain_id is domain
            else row
            for row in registry.statement.domains
        )
        changed = registry.model_copy(
            update={
                "statement": registry.statement.model_copy(
                    update={"domains": changed_rows}
                )
            }
        )
        with pytest.raises(ValueError, match="recursive signed infrastructure"):
            authority_module.validate_capsule_signed_binding_index(
                capsule,
                index,
                bindings,
                digest_registry=changed,
            )


def test_missing_swapped_or_cyclic_signed_binding_fails_closed() -> None:
    capsule, index, bindings = _c1_capsule_graph()
    registry = decode_digest_domain_registry_toml(_DIGEST_REGISTRY.read_bytes())
    cases = (
        bindings[:-1],
        (
            bindings[0].model_copy(update={"binding_ref": bindings[1].binding_ref}),
            *bindings[1:],
        ),
        (
            *bindings,
            _c1_signed_binding(
                index.index_ref,
                role=TrustRole.FOUNDRY_TRUST_ROOT,
                evidence_label="cycle",
            ),
        ),
    )
    for candidate in cases:
        with pytest.raises(ValueError, match="signed binding graph"):
            authority_module.validate_capsule_signed_binding_index(
                capsule,
                index,
                tuple(candidate),
                digest_registry=registry,
            )


def test_imported_signed_evidence_rejects_regenerated_manifest_or_swapped_ref() -> None:
    raw = b'{"schema_version":"polisyos.foundry.production-data-custody.v1"}'
    record = record_ref(
        DigestDomain.PRODUCTION_CUSTODY,
        raw,
        schema_version="polisyos.foundry.production-data-custody.v1",
    )
    evidence = authority_module.ExactSignedArtifactEvidenceStatement(
        schema_version="polisyos.foundry.signed-artifact-evidence.v1",
        signed_blob_bytes=raw,
        exact_manifest_bytes=b"original-manifest",
        detached_signature_bytes=b"original-signature",
    )
    binding = _c1_signed_binding(
        record,
        role=TrustRole.CUSTODY_VERIFIER,
        evidence_label="unused",
    )
    evidence_ref = record_ref(
        DigestDomain.SIGNED_EVIDENCE,
        canonical_json_bytes(evidence.model_dump(mode="json")),
        schema_version=evidence.schema_version,
    )
    binding = binding.model_copy(
        update={
            "statement": binding.statement.model_copy(
                update={"signed_evidence_ref": evidence_ref}
            )
        },
    )
    binding = binding.model_copy(
        update={
            "binding_ref": authority_module.build_foundry_statement_ref(
                DigestDomain.SIGNED_RECORD_BINDING,
                binding.statement,
            )
        },
    )
    authority_module.validate_exact_signed_record(binding, evidence)
    for mutation in (
        evidence.model_copy(update={"exact_manifest_bytes": b"regenerated"}),
        evidence.model_copy(update={"detached_signature_bytes": b"swapped"}),
    ):
        with pytest.raises(ValueError, match="signed evidence"):
            authority_module.validate_exact_signed_record(binding, mutation)


def test_build_lineage_requires_owner_resolved_build_verifier_trust() -> None:
    required_fields = {
        "trust_resolution_receipt_ref",
        "verifier_provenance_ref",
    }
    assert required_fields <= set(
        authority_module.evidence_module.BuildLineageStatement.model_fields
    )
    build_ref = _c1_ref(DigestDomain.BUILD_LINEAGE, "lineage")
    binding = _c1_signed_binding(
        build_ref,
        role=TrustRole.BUILD_VERIFIER,
        evidence_label="lineage",
    )
    assert binding.statement.required_role is TrustRole.BUILD_VERIFIER
    assert binding.statement.verification_basis.kind == "resolved_trust"


def test_generated_launchers_normalize_only_admitted_interpreter_across_roots() -> None:
    target = "polisyos.tools:main"
    left = authority_module.evidence_module.produce_posix_console_launcher(
        interpreter=Path("/tmp/checkout-a/.venv/bin/python"),
        entrypoint_target=target,
        normalized_flags=("-I",),
    )
    right = authority_module.evidence_module.produce_posix_console_launcher(
        interpreter=Path("/opt/task/checkout-b/.venv/bin/python"),
        entrypoint_target=target,
        normalized_flags=("-I",),
    )
    normalized_left = authority_module.evidence_module.verify_posix_console_launcher(
        left,
        admitted_interpreter=Path("/tmp/checkout-a/.venv/bin/python"),
        entrypoint_target=target,
        normalized_flags=("-I",),
    )
    normalized_right = authority_module.evidence_module.verify_posix_console_launcher(
        right,
        admitted_interpreter=Path("/opt/task/checkout-b/.venv/bin/python"),
        entrypoint_target=target,
        normalized_flags=("-I",),
    )
    assert normalized_left == normalized_right
    assert b"@PYTHON@" in normalized_left
    assert b"checkout-a" not in normalized_left
    assert b"checkout-b" not in normalized_right


def test_launcher_body_crlf_flags_stub_or_second_interpreter_mutation_rejects() -> None:
    interpreter = Path("/tmp/environment/bin/python")
    target = "polisyos.tools:main"
    baseline = authority_module.evidence_module.produce_posix_console_launcher(
        interpreter=interpreter,
        entrypoint_target=target,
        normalized_flags=("-I",),
    )
    mutations = (
        baseline.replace(b"\n", b"\r\n"),
        baseline.replace(b" -I\n", b" -s\n", 1),
        baseline.replace(b"import re\n", b"import os\n", 1),
        baseline + f"# {interpreter}\n".encode(),
    )
    for mutated in mutations:
        with pytest.raises(ValueError, match="launcher"):
            authority_module.evidence_module.verify_posix_console_launcher(
                mutated,
                admitted_interpreter=interpreter,
                entrypoint_target=target,
                normalized_flags=("-I",),
            )


def test_path_like_payload_bytes_are_never_launcher_normalized() -> None:
    payload = b"config=/tmp/environment/bin/python\n"
    row = authority_module.evidence_module.StablePayloadFileRow(
        row_kind="payload",
        logical_root="purelib",
        relative_path=RootedRelativePath(value="package/config.txt"),
        byte_length=len(payload),
        raw_content_hash=domain_digest(DigestDomain.RAW_BLOB, payload),
    )
    assert authority_module.evidence_module.normalize_installed_file_bytes(
        row,
        payload,
        admitted_interpreter=Path("/tmp/environment/bin/python"),
    ) == payload


def test_noneditable_root_install_is_stable_across_sibling_checkout_paths() -> None:
    raw = b"from .api import run\n"
    rows = (
        authority_module.evidence_module.StablePayloadFileRow(
            row_kind="payload",
            logical_root="purelib",
            relative_path=RootedRelativePath(value="polisyos/__init__.py"),
            byte_length=len(raw),
            raw_content_hash=domain_digest(DigestDomain.RAW_BLOB, raw),
        ),
    )
    left = authority_module.evidence_module.build_noneditable_stable_manifest(
        normalized_name="policy-engine",
        version="0.1.0",
        rows=rows,
        source_checkout=Path("/tmp/checkout-a"),
    )
    right = authority_module.evidence_module.build_noneditable_stable_manifest(
        normalized_name="policy-engine",
        version="0.1.0",
        rows=rows,
        source_checkout=Path("/opt/checkout-b"),
    )
    assert left == right


def test_editable_root_install_is_rejected_from_n8_identity() -> None:
    editable = authority_module.evidence_module.StablePayloadFileRow(
        row_kind="payload",
        logical_root="purelib",
        relative_path=RootedRelativePath(
            value="policy_engine-0.1.0.dist-info/direct_url.json"
        ),
        byte_length=2,
        raw_content_hash=domain_digest(DigestDomain.RAW_BLOB, b"{}"),
    )
    with pytest.raises(ValueError, match="editable"):
        authority_module.evidence_module.build_noneditable_stable_manifest(
            normalized_name="policy-engine",
            version="0.1.0",
            rows=(editable,),
            source_checkout=Path("/tmp/checkout"),
        )


def test_substituted_uv_bytes_fail_against_unchanged_owner_admission() -> None:
    declaration = load_dependency_profile_registry(_PROFILE_REGISTRY).declarations[0]
    admission = _admission(declaration)
    authority_module.validate_admitted_uv_executable(
        admission,
        b"candidate-uv-executable",
    )
    with pytest.raises(ValueError, match="uv executable"):
        authority_module.validate_admitted_uv_executable(
            admission,
            b"substituted-uv-executable",
        )


def test_arbitrary_cache_receipt_is_not_an_authority_input() -> None:
    profile_parameters = inspect.signature(resolve_dependency_profile).parameters
    authority_parameters = inspect.signature(
        authority_module.MethodCatalogDependencyAuthority.resolve
    ).parameters
    assert "cache_receipt" not in profile_parameters
    assert "cache_receipt" not in authority_parameters
    assert "uv_cache_dir" not in authority_parameters


def test_required_file_mutation_with_unchanged_dist_info_fails_reconciliation(
    tmp_path: Path,
) -> None:
    profile = _resolve_tracked_profile()
    first = profile.distributions[0]
    changed = domain_digest(
        DigestDomain.SELECTED_DISTRIBUTION,
        b"same-dist-info-different-required-file",
    )
    fixture = _candidate_environment_fixture(
        tmp_path,
        profile,
        label="mutated-file",
        selected_overrides={first.name: (first.version, changed)},
    )
    result = reconcile_bound_installed_environment(
        profile,
        environment_root=fixture.root,
        environment_receipt=fixture.receipt,
        evidence=fixture.evidence,
    )
    assert result.status == "fail"
    assert any(
        failure.code is AuthorityFailureCode.CONTENT_MISMATCH
        for failure in result.failures
    )


def test_influential_marker_or_lock_edge_cannot_be_omitted() -> None:
    baseline = _resolve_tracked_profile()
    lock = (_PRODUCT_ROOT / "uv.lock").read_bytes()
    selected = baseline.distributions[-1]
    needle = f'name = "{selected.name}"\nversion = "{selected.version}"'.encode()
    assert lock.count(needle) == 1
    changed_lock = lock.replace(needle, b'name = "omitted-edge"\nversion = "0"', 1)
    declaration = baseline.declaration.model_copy(
        update={"lockfile_ref": domain_digest(DigestDomain.UV_LOCK, changed_lock)}
    )
    result = resolve_dependency_profile(
        declaration,
        pyproject_bytes=(_PRODUCT_ROOT / "pyproject.toml").read_bytes(),
        lockfile_bytes=changed_lock,
        marker_environment=_marker_environment(),
        production_data_manifest=ProductionDataManifestPresent(
            kind="present",
            exact_bytes=b"{}",
        ),
        admission=_admission(declaration),
    )
    assert not isinstance(result, ResolvedMethodCatalogDependencyProfile)


def test_two_fresh_installs_share_closure_but_not_instance_receipt() -> None:
    profile = _resolve_tracked_profile()
    statements = []
    for label in ("instance-a", "instance-b"):
        marker = authority_module.evidence_module.DependencyEnvironmentMarkerStatement(
            schema_version="polisyos.foundry.dependency-environment-marker.v1",
            environment_creation_nonce=domain_digest(
                DigestDomain.ENVIRONMENT_INSTANCE,
                label.encode(),
            ),
            stable_closure=profile.stable_closure,
            source_authority_ref=_c1_ref(DigestDomain.CANONICAL_SOURCE, "source"),
            python_runtime_ref=_c1_ref(DigestDomain.TOOLCHAIN_RUNTIME, "python"),
            python_runtime_installation_ref=_c1_ref(
                DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION,
                label,
            ),
            observed_python_runtime_ref=_c1_ref(
                DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED,
                label,
            ),
            python_runtime_verification_ref=_c1_ref(
                DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION,
                label,
            ),
            uv_executable_ref=_c1_ref(DigestDomain.TOOLCHAIN_EXECUTABLE, "uv"),
            derived_uv_argv=domain_digest(DigestDomain.DERIVED_UV_ARGV, b"argv"),
            instance_content_set=domain_digest(
                DigestDomain.CONTENT_SET_INSTANCE,
                label.encode(),
            ),
        )
        statements.append(
            record_ref(
                DigestDomain.ENVIRONMENT_MARKER,
                canonical_json_bytes(marker.model_dump(mode="json")),
                schema_version=marker.schema_version,
            )
        )
    assert statements[0] != statements[1]
    assert profile.stable_closure == _resolve_tracked_profile().stable_closure


def test_tooling_pythonpath_cannot_supply_n8_distribution_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _resolve_tracked_profile()
    monkeypatch.setenv("PYTHONPATH", "/tmp/forged-tooling-site-packages")
    observed = _resolve_tracked_profile()
    assert observed.stable_closure == baseline.stable_closure
    assert observed.distributions == baseline.distributions


def test_manifest_missing_candidate_preserves_exact_missing_or_unreadable_cause() -> None:
    declaration = load_dependency_profile_registry(_PROFILE_REGISTRY).declarations[0]
    outcomes = tuple(
        resolve_dependency_profile(
            declaration,
            pyproject_bytes=b"not-read",
            lockfile_bytes=b"not-read",
            marker_environment={},
            production_data_manifest=ProductionDataManifestUnavailable(
                kind="unavailable",
                cause=cause,
            ),
            admission=_admission(declaration),
        )
        for cause in ("missing", "unreadable")
    )
    assert tuple(row.cause for row in outcomes) == ("missing", "unreadable")
    assert {row.code for row in outcomes} == {AuthorityFailureCode.MANIFEST_MISSING}


def test_public_builders_reject_caller_constructed_positive_profile() -> None:
    from polisyos.foundry.methods.catalog.snapshot import (
        build_method_catalog_runtime_identity,
    )

    with pytest.raises(TypeError, match="unexpected keyword"):
        build_method_catalog_runtime_identity(
            object(),  # type: ignore[arg-type]
            dependency_authority_request=_authority_request(Path("/tmp")),
            admitted_profile=_resolve_tracked_profile(),  # type: ignore[call-arg]
        )


def test_alternate_git_root_with_self_consistent_registries_cannot_redirect_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    alternate = tmp_path / "alternate"
    alternate.mkdir()
    _git_at(alternate, "init", "-b", "alternate")
    _git_at(alternate, "config", "user.name", "alternate")
    _git_at(alternate, "config", "user.email", "alternate@example.invalid")
    (alternate / "README.md").write_text("self-consistent decoy\n", encoding="utf-8")
    _git_at(alternate, "add", "README.md")
    _git_at(alternate, "commit", "-m", "decoy")
    monkeypatch.chdir(alternate)
    monkeypatch.setenv("GIT_DIR", str(alternate / ".git"))
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(
        result,
        authority_module.SourceUnestablishedMethodCatalogDependencyProfile,
    )
    assert result.result_kind is NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED
    assert result.failure.failure_code is AuthorityFailureCode.SOURCE_NOT_ESTABLISHED


def test_dirty_authority_registry_under_unchanged_head_fails_before_admission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    authority_registry = (
        product_root
        / "architecture"
        / "production_quality"
        / "method_catalog_dependency_authority.toml"
    )
    authority_registry.write_text(
        authority_registry.read_text(encoding="utf-8") + "\n# dirty authority\n",
        encoding="utf-8",
    )
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert result.result_kind is NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED
    assert result.failure.failure_code is AuthorityFailureCode.SOURCE_NOT_ESTABLISHED


def test_no_runtime_cutoff_preflight_blocks_before_sync_or_candidate_generation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path,
    )
    crossed: list[str] = []

    def forbidden(*_args: object, **_kwargs: object) -> None:
        crossed.append("candidate")
        pytest.fail("candidate/sync edge crossed before cutoff preflight")

    for name in (
        "_open_owner_python_runtime_installation_authority",
        "_open_owner_python_runtime_observer",
        "_open_production_dependency_authority_repository",
        "resolve_dependency_profile",
        "reconcile_bound_installed_environment",
    ):
        monkeypatch.setattr(authority_module, name, forbidden)
    result = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(result, UnestablishedMethodCatalogDependencyProfile)
    assert crossed == []


def test_restoring_legacy_ambient_or_candidate_projection_fails_cross_file_strangle(
    tmp_path: Path,
) -> None:
    source = (
        _PRODUCT_ROOT / "src/polisyos/foundry/methods/catalog/snapshot.py"
    ).read_text(encoding="utf-8")
    mutant = tmp_path / "snapshot.py"
    mutant.write_text(
        source.replace(
            "    del snapshot\n    return build_production_method_catalog_dependency_authority().resolve(",
            "    _build_candidate_method_catalog_runtime_identity(snapshot)\n"
            "    return build_production_method_catalog_dependency_authority().resolve(",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="public catalog negative graph"):
        authority_module.validate_public_catalog_negative_graph(
            snapshot_file=mutant,
            scan_roots=(),
        )


def test_sibling_resolution_dto_codec_domain_or_writer_enlarges_complete_denominator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _RoguePositiveResolution(FoundryAuthorityModel):
        schema_version: Literal["polisyos.foundry.rogue-positive-resolution.v1"]
        status: Literal["resolved"]

    monkeypatch.setattr(
        authority_module,
        "MethodCatalogDependencyAuthorityResult",
        Annotated[
            authority_module.SourceRejectedMethodCatalogDependencyProfile
            | authority_module.SourceUnestablishedMethodCatalogDependencyProfile
            | authority_module.UnestablishedMethodCatalogDependencyProfile
            | _RoguePositiveResolution,
            authority_module.Field(discriminator="status"),
        ],
    )
    with pytest.raises(AssertionError, match="result denominator"):
        authority_module.validate_negative_only_dependency_authority_abi()


def _candidate_runtime_tree(tmp_path: Path) -> tuple[Path, Path]:
    runtime_root = tmp_path / "runtime"
    executable = runtime_root / "bin" / "python"
    early_stdlib = runtime_root / "lib" / "python3.14" / "a_early.py"
    late_stdlib = runtime_root / "lib" / "python3.14" / "z_late.py"
    executable.parent.mkdir(parents=True)
    early_stdlib.parent.mkdir(parents=True)
    executable.write_bytes(b"candidate-python-launcher\n")
    early_stdlib.write_bytes(b"EARLY = 1\n")
    late_stdlib.write_bytes(b"LATE = 1\n")
    return runtime_root, early_stdlib


def _observe_candidate_runtime(
    runtime_root: Path,
    *,
    nonce_label: str = "instance",
    hooks: object | None = None,
) -> object:
    return authority_module.observe_candidate_python_runtime(
        environment_root=runtime_root,
        runtime_root=runtime_root,
        environment_creation_nonce=domain_digest(
            DigestDomain.ENVIRONMENT_INSTANCE,
            nonce_label.encode(),
        ),
        executable_relative_path=RootedRelativePath(value="bin/python"),
        version="3.14.0",
        platform_tag="macosx_15_0_arm64",
        abi_tag="cp314",
        digest_registry=decode_digest_domain_registry_toml(
            _DIGEST_REGISTRY.read_bytes()
        ),
        hooks=hooks,
    )


def test_nested_stdlib_mutation_during_first_walk_is_runtime_not_established(
    tmp_path: Path,
) -> None:
    runtime_root, early_stdlib = _candidate_runtime_tree(tmp_path)

    def mutate_after_hash_before_fstat() -> None:
        early_stdlib.write_bytes(b"EARLY = 2\n")

    result = _observe_candidate_runtime(
        runtime_root,
        hooks=authority_module.CandidateRuntimeObservationHooks(
            relative_path=RootedRelativePath(value="lib/python3.14/a_early.py"),
            before_first_post_fstat=mutate_after_hash_before_fstat,
        ),
    )
    assert isinstance(result, BidirectionalUnestablishedAuthorityPredicate)
    assert result.predicate_id is AuthorityPredicateId.PYTHON_RUNTIME
    assert result.failure_code is AuthorityFailureCode.PYTHON_RUNTIME_NOT_ESTABLISHED


def test_barriered_write_after_second_post_fstat_preserves_equal_candidate_manifests(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, early_stdlib = _candidate_runtime_tree(tmp_path)
    rendezvous = Barrier(2)
    observations: list[object] = []

    def expose_post_observation_window() -> None:
        rendezvous.wait(timeout=5)
        rendezvous.wait(timeout=5)

    def observe() -> None:
        observations.append(
            _observe_candidate_runtime(
                runtime_root,
                hooks=authority_module.CandidateRuntimeObservationHooks(
                    relative_path=RootedRelativePath(
                        value="lib/python3.14/a_early.py"
                    ),
                    after_second_post_fstat=expose_post_observation_window,
                ),
            )
        )

    worker = Thread(target=observe)
    worker.start()
    rendezvous.wait(timeout=5)
    early_stdlib.write_bytes(b"EARLY = escaped\n")
    escaped_bytes = early_stdlib.read_bytes()
    rendezvous.wait(timeout=5)
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert len(observations) == 1
    candidate = observations[0]
    assert isinstance(candidate, authority_module.CandidatePythonRuntimeObservation)
    identity = candidate.root_identity
    assert identity.first_walk_manifest_ref == identity.second_walk_manifest_ref
    assert (
        identity.opened_before
        == identity.opened_after_enumeration
        == identity.reopened_by_path
    )
    escaped_hash = domain_digest(DigestDomain.RAW_BLOB, escaped_bytes)
    early_row = next(
        row
        for row in candidate.second_manifest.files
        if row.relative_path.value == "lib/python3.14/a_early.py"
    )
    assert early_row.content_hash != escaped_hash

    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path / "production-check",
    )
    production = build_production_method_catalog_dependency_authority().resolve(
        _authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(production, UnestablishedMethodCatalogDependencyProfile)
    _assert_current_cutoff_refusal(production)


def test_control_write_before_second_post_fstat_changes_candidate_manifest(
    tmp_path: Path,
) -> None:
    runtime_root, early_stdlib = _candidate_runtime_tree(tmp_path)

    def mutate_before_post_fstat() -> None:
        early_stdlib.write_bytes(b"EARLY = detected\n")

    result = _observe_candidate_runtime(
        runtime_root,
        hooks=authority_module.CandidateRuntimeObservationHooks(
            relative_path=RootedRelativePath(value="lib/python3.14/a_early.py"),
            before_second_post_fstat=mutate_before_post_fstat,
        ),
    )
    assert isinstance(result, BidirectionalUnestablishedAuthorityPredicate)
    assert result.failure_code is AuthorityFailureCode.PYTHON_RUNTIME_NOT_ESTABLISHED


def test_unsupported_or_unstable_filesystem_is_runtime_not_established(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, _early_stdlib = _candidate_runtime_tree(tmp_path)
    monkeypatch.setattr(
        authority_module,
        "_detect_candidate_runtime_filesystem_kind",
        lambda _root: None,
    )
    result = _observe_candidate_runtime(runtime_root)
    assert isinstance(result, BidirectionalUnestablishedAuthorityPredicate)
    assert result.failure_code is AuthorityFailureCode.PYTHON_RUNTIME_NOT_ESTABLISHED


def test_candidate_two_pass_observation_has_no_positive_production_intake(
    tmp_path: Path,
) -> None:
    runtime_root, _early_stdlib = _candidate_runtime_tree(tmp_path)
    candidate = _observe_candidate_runtime(runtime_root)
    assert isinstance(candidate, authority_module.CandidatePythonRuntimeObservation)
    assert "candidate" in candidate.root_identity.predicate_class
    production_parameters = inspect.signature(
        authority_module.build_production_method_catalog_dependency_authority
    ).parameters
    assert tuple(production_parameters) == ()
    assert "candidate_runtime_observation" not in production_parameters


def test_moved_replaced_or_byte_identical_copied_runtime_root_changes_token(
    tmp_path: Path,
) -> None:
    runtime_root, _early_stdlib = _candidate_runtime_tree(tmp_path)
    original = _observe_candidate_runtime(runtime_root, nonce_label="same")
    assert isinstance(original, authority_module.CandidatePythonRuntimeObservation)

    copied_root = tmp_path / "copy"
    shutil.copytree(runtime_root, copied_root)
    copied = _observe_candidate_runtime(copied_root, nonce_label="same")
    assert isinstance(copied, authority_module.CandidatePythonRuntimeObservation)

    moved_root = tmp_path / "moved"
    runtime_root.rename(moved_root)
    moved = _observe_candidate_runtime(moved_root, nonce_label="same")
    assert isinstance(moved, authority_module.CandidatePythonRuntimeObservation)
    assert len({original.root_token, copied.root_token, moved.root_token}) == 3


def test_posix_runtime_root_token_recomputes_open_handle_path_and_race_relation(
    tmp_path: Path,
) -> None:
    runtime_root, _early_stdlib = _candidate_runtime_tree(tmp_path)
    candidate = _observe_candidate_runtime(runtime_root)
    assert isinstance(candidate, authority_module.CandidatePythonRuntimeObservation)
    recomputed = authority_module.build_foundry_statement_ref(
        DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN,
        candidate.root_identity,
    ).semantic_hash
    assert candidate.root_token == recomputed
    changed_path = candidate.root_identity.model_copy(
        update={
            "runtime_root_path_hash": domain_digest(
                DigestDomain.TOOLCHAIN_RUNTIME_ROOT_PATH,
                b"different-realpath",
            )
        }
    )
    assert (
        authority_module.build_foundry_statement_ref(
            DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN,
            changed_path,
        ).semantic_hash
        != candidate.root_token
    )


def _candidate_runtime_owner_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    runtime_root: Path,
    *,
    nonce_label: str = "installation",
) -> tuple[
    authority_module.CanonicalFoundrySourceAuthority,
    authority_module.CandidatePythonRuntimeInstallation,
    authority_module._ProductionPythonRuntimeObserver,
    authority_module.PythonRuntimeAdmission,
]:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path / "source-fixture",
    )
    source = authority_module._build_production_canonical_source_resolver().resolve(
        request=_authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(source, authority_module.CanonicalFoundrySourceAuthority)
    with authority_module._unwrap_owner_capability(
        source,
        authority_module._CANONICAL_SOURCE_SPEC,
    ) as source_payload:
        observation = authority_module.observe_candidate_python_runtime(
            environment_root=runtime_root,
            runtime_root=runtime_root,
            environment_creation_nonce=domain_digest(
                DigestDomain.ENVIRONMENT_INSTANCE,
                nonce_label.encode(),
            ),
            executable_relative_path=RootedRelativePath(value="bin/python"),
            version="3.14",
            platform_tag="macosx_15_0_arm64",
            abi_tag="cp314",
            digest_registry=source_payload.digest_registry,
        )
        assert isinstance(
            observation,
            authority_module.CandidatePythonRuntimeObservation,
        )
        source_binding = authority_module.evidence_module.PythonRuntimeSourceBindingStatement(
            schema_version="polisyos.foundry.python-runtime-source-binding.v1",
            selected_artifact_ref=_c1_ref(
                DigestDomain.TOOLCHAIN_SELECTED,
                "python-artifact",
            ),
            runtime_manifest_ref=observation.root_identity.second_walk_manifest_ref,
            installation_transform="python_runtime_installation_v1",
        )
        admission = authority_module.PythonRuntimeAdmission(
            artifact_role="python_runtime",
            version="3.14",
            platform_tag="macosx_15_0_arm64",
            selected_artifact_ref=source_binding.selected_artifact_ref,
            executable_blob_ref=_c1_ref(
                DigestDomain.TOOLCHAIN_EXECUTABLE,
                "python-executable",
            ),
            expected_runtime_manifest_ref=(
                observation.root_identity.second_walk_manifest_ref
            ),
            expected_runtime_source_binding_ref=(
                authority_module.build_foundry_statement_ref(
                    DigestDomain.TOOLCHAIN_RUNTIME_BINDING,
                    source_binding,
                )
            ),
            verifier_provenance_ref=_c1_ref(
                DigestDomain.VERIFIER_PROVENANCE,
                "runtime-verifier",
            ),
        )
        installation = authority_module.build_candidate_python_runtime_installation(
            source_authority=source_payload,
            environment_root=runtime_root,
            admission=admission,
            environment_creation_nonce=domain_digest(
                DigestDomain.ENVIRONMENT_INSTANCE,
                nonce_label.encode(),
            ),
            installer_provenance_ref=_c1_ref(
                DigestDomain.VERIFIER_PROVENANCE,
                "runtime-installer",
            ),
        )
        assert isinstance(
            installation,
            authority_module.CandidatePythonRuntimeInstallation,
        )
        observer = authority_module._ProductionPythonRuntimeObserver(
            source_authority=source_payload
        )
    return source, installation, observer, admission


def test_fresh_n8_resolves_marker_installation_before_runtime_observation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, _early_stdlib = _candidate_runtime_tree(tmp_path)
    source, installation, _production_observer, admission = (
        _candidate_runtime_owner_fixture(
            monkeypatch,
            tmp_path,
            runtime_root,
        )
    )
    profile = _resolve_tracked_profile()
    fixture = _candidate_environment_fixture(
        tmp_path,
        profile,
        label=runtime_root.name,
        python_runtime_ref=admission.expected_runtime_manifest_ref,
        runtime_installation_ref=installation.persisted.receipt_ref,
    )
    events: list[str] = []
    terminal = authority_module._candidate_runtime_not_established(
        decode_digest_domain_registry_toml(_DIGEST_REGISTRY.read_bytes())
    )

    class _RecordingInstallationAuthority:
        def resolve_installed_root(
            self,
            *,
            environment_root: Path,
            receipt_ref: authority_module.FoundryRecordRef[
                Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]
            ],
            admission: authority_module.PythonRuntimeAdmission,
        ) -> object:
            events.append("resolve_installed_root")
            assert environment_root == runtime_root
            assert receipt_ref == fixture.marker.python_runtime_installation_ref
            assert admission is not None
            return installation.capability

    class _RecordingObserver:
        def observe_and_verify(
            self,
            *,
            environment_root: Path,
            installation: authority_module.ResolvedPythonRuntimeInstallation,
            admission: authority_module.PythonRuntimeAdmission,
        ) -> object:
            events.append("observe_and_verify")
            assert environment_root == runtime_root
            assert isinstance(
                installation,
                authority_module.ResolvedPythonRuntimeInstallation,
            )
            assert admission is not None
            return terminal

    try:
        result = authority_module._resolve_marked_python_runtime_before_observation(
            environment_root=runtime_root,
            environment_receipt=fixture.receipt,
            evidence=fixture.evidence,
            installation_authority=_RecordingInstallationAuthority(),
            observer=_RecordingObserver(),
            admission=admission,
        )
        assert result is terminal
        assert events == ["resolve_installed_root", "observe_and_verify"]
        authority_module.validate_public_catalog_negative_graph()
    finally:
        _release_candidate_runtime_owner(source)


def _release_candidate_runtime_owner(
    source: authority_module.CanonicalFoundrySourceAuthority,
    *installations: authority_module.CandidatePythonRuntimeInstallation,
) -> None:
    for installation in installations:
        authority_module._release_owner_capability(
            installation.capability,
            authority_module._RUNTIME_INSTALLATION_SPEC,
        )
    authority_module._release_owner_capability(
        source,
        authority_module._CANONICAL_SOURCE_SPEC,
    )


def test_runtime_observer_requires_owner_sealed_installation_capability(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, _early_stdlib = _candidate_runtime_tree(tmp_path)
    source, installation, observer, admission = _candidate_runtime_owner_fixture(
        monkeypatch,
        tmp_path,
        runtime_root,
    )
    try:
        for fake in (
            object(),
            object.__new__(authority_module.ResolvedPythonRuntimeInstallation),
        ):
            result = observer.observe_and_verify(
                environment_root=runtime_root,
                installation=fake,  # type: ignore[arg-type]
                admission=admission,
            )
            assert isinstance(result, BidirectionalUnestablishedAuthorityPredicate)
            assert result.predicate_id is AuthorityPredicateId.PYTHON_RUNTIME
            assert (
                result.failure_code
                is AuthorityFailureCode.PYTHON_RUNTIME_NOT_ESTABLISHED
            )
    finally:
        _release_candidate_runtime_owner(source, installation)


def test_runtime_observer_derives_child_executable_root_and_source_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, _early_stdlib = _candidate_runtime_tree(tmp_path)
    source, installation, observer, admission = _candidate_runtime_owner_fixture(
        monkeypatch,
        tmp_path,
        runtime_root,
    )
    verified: object | None = None
    try:
        verified = observer.observe_and_verify(
            environment_root=runtime_root,
            installation=installation.capability,
            admission=admission,
        )
        assert isinstance(verified, authority_module.VerifiedPythonRuntime)
        with authority_module._unwrap_owner_capability(
            verified,
            authority_module._VERIFIED_RUNTIME_SPEC,
        ) as payload:
            assert (
                payload.observed_ref.semantic_hash.domain
                is DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED
            )
            assert (
                payload.verification_ref.semantic_hash.domain
                is DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION
            )
    finally:
        if isinstance(verified, authority_module.VerifiedPythonRuntime):
            authority_module._release_owner_capability(
                verified,
                authority_module._VERIFIED_RUNTIME_SPEC,
            )
        _release_candidate_runtime_owner(source, installation)


def test_observed_python_runtime_cannot_copy_expected_runtime_ref(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, early_stdlib = _candidate_runtime_tree(tmp_path)
    source, installation, observer, admission = _candidate_runtime_owner_fixture(
        monkeypatch,
        tmp_path,
        runtime_root,
    )
    try:
        early_stdlib.write_bytes(b"MUTATED AFTER INSTALLATION\n")
        result = observer.observe_and_verify(
            environment_root=runtime_root,
            installation=installation.capability,
            admission=admission,
        )
        assert isinstance(result, RejectedAuthorityPredicate)
        assert result.failure_code is AuthorityFailureCode.PYTHON_RUNTIME_MISMATCH
    finally:
        _release_candidate_runtime_owner(source, installation)


def test_python_stdlib_mutation_with_unchanged_launcher_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, early_stdlib = _candidate_runtime_tree(tmp_path)
    launcher_before = (runtime_root / "bin" / "python").read_bytes()
    source, installation, observer, admission = _candidate_runtime_owner_fixture(
        monkeypatch,
        tmp_path,
        runtime_root,
    )
    try:
        early_stdlib.write_bytes(b"STDLIB = changed\n")
        assert (runtime_root / "bin" / "python").read_bytes() == launcher_before
        result = observer.observe_and_verify(
            environment_root=runtime_root,
            installation=installation.capability,
            admission=admission,
        )
        assert isinstance(result, RejectedAuthorityPredicate)
        assert result.failure_code is AuthorityFailureCode.PYTHON_RUNTIME_MISMATCH
    finally:
        _release_candidate_runtime_owner(source, installation)


def test_byte_identical_child_redirected_to_unbound_runtime_root_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, _early_stdlib = _candidate_runtime_tree(tmp_path)
    source, installation, observer, admission = _candidate_runtime_owner_fixture(
        monkeypatch,
        tmp_path,
        runtime_root,
    )
    redirected_root = tmp_path / "redirected"
    shutil.copytree(runtime_root, redirected_root)
    child = runtime_root / "bin" / "python"
    child.unlink()
    child.symlink_to(redirected_root / "bin" / "python")
    try:
        result = observer.observe_and_verify(
            environment_root=runtime_root,
            installation=installation.capability,
            admission=admission,
        )
        assert isinstance(result, RejectedAuthorityPredicate)
        assert result.failure_code is AuthorityFailureCode.PYTHON_RUNTIME_MISMATCH
    finally:
        _release_candidate_runtime_owner(source, installation)


def test_copied_runtime_tree_cannot_rewrite_owner_installation_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, _early_stdlib = _candidate_runtime_tree(tmp_path)
    source, installation, _observer, _admission = _candidate_runtime_owner_fixture(
        monkeypatch,
        tmp_path,
        runtime_root,
    )
    copied_root = tmp_path / "copied"
    shutil.copytree(runtime_root, copied_root)
    copied_observation = _observe_candidate_runtime(copied_root)
    assert isinstance(
        copied_observation,
        authority_module.CandidatePythonRuntimeObservation,
    )
    forged = installation.persisted.model_copy(
        update={
            "statement": installation.persisted.statement.model_copy(
                update={
                    "runtime_root_identity": copied_observation.root_identity,
                    "runtime_root_instance": copied_observation.root_token,
                }
            )
        }
    )
    try:
        with pytest.raises(ValueError, match="installation receipt"):
            authority_module.validate_python_runtime_installation(forged)
    finally:
        _release_candidate_runtime_owner(source, installation)


def test_fresh_runtime_root_resolution_changes_instance_not_stable_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    left_root, _early_stdlib = _candidate_runtime_tree(tmp_path / "left")
    right_root = tmp_path / "right" / "runtime"
    right_root.parent.mkdir(parents=True)
    shutil.copytree(left_root, right_root)
    source, left, observer, admission = _candidate_runtime_owner_fixture(
        monkeypatch,
        tmp_path,
        left_root,
        nonce_label="left-instance",
    )
    with authority_module._unwrap_owner_capability(
        source,
        authority_module._CANONICAL_SOURCE_SPEC,
    ) as source_payload:
        right = authority_module.build_candidate_python_runtime_installation(
            source_authority=source_payload,
            environment_root=right_root,
            admission=admission,
            environment_creation_nonce=domain_digest(
                DigestDomain.ENVIRONMENT_INSTANCE,
                b"right-instance",
            ),
            installer_provenance_ref=_c1_ref(
                DigestDomain.VERIFIER_PROVENANCE,
                "runtime-installer",
            ),
        )
    assert isinstance(right, authority_module.CandidatePythonRuntimeInstallation)
    left_verified: object | None = None
    right_verified: object | None = None
    try:
        assert (
            left.persisted.statement.runtime_manifest_ref
            == right.persisted.statement.runtime_manifest_ref
        )
        assert (
            left.persisted.statement.runtime_source_binding_ref
            == right.persisted.statement.runtime_source_binding_ref
        )
        assert (
            left.persisted.statement.runtime_root_instance
            != right.persisted.statement.runtime_root_instance
        )
        left_verified = observer.observe_and_verify(
            environment_root=left_root,
            installation=left.capability,
            admission=admission,
        )
        right_verified = observer.observe_and_verify(
            environment_root=right_root,
            installation=right.capability,
            admission=admission,
        )
        assert isinstance(left_verified, authority_module.VerifiedPythonRuntime)
        assert isinstance(right_verified, authority_module.VerifiedPythonRuntime)
        with (
            authority_module._unwrap_owner_capability(
                left_verified,
                authority_module._VERIFIED_RUNTIME_SPEC,
            ) as left_payload,
            authority_module._unwrap_owner_capability(
                right_verified,
                authority_module._VERIFIED_RUNTIME_SPEC,
            ) as right_payload,
        ):
            assert left_payload.observed_ref != right_payload.observed_ref
            assert left_payload.verification_ref != right_payload.verification_ref
    finally:
        for verified in (left_verified, right_verified):
            if isinstance(verified, authority_module.VerifiedPythonRuntime):
                authority_module._release_owner_capability(
                    verified,
                    authority_module._VERIFIED_RUNTIME_SPEC,
                )
        _release_candidate_runtime_owner(source, left, right)


def _candidate_production_root_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[
    authority_module.CanonicalFoundrySourceAuthority,
    authority_module.VerifiedProductionDataAppointment,
    Path,
    authority_module.evidence_module.ExternalAuthorityRef[
        Literal[authority_module.ExternalAuthorityKind.INSTITUTIONAL_ROOT]
    ],
]:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path / "source-fixture",
    )
    source = authority_module._build_production_canonical_source_resolver().resolve(
        request=_authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(source, authority_module.CanonicalFoundrySourceAuthority)
    root = tmp_path / "appointed-production-data"
    root.mkdir()
    manifest_bytes = b'{"catalog":"appointed"}\n'
    (root / "manifest.json").write_bytes(manifest_bytes)
    root_ref = _c1_external_ref(
        authority_module.ExternalAuthorityKind.INSTITUTIONAL_ROOT,
        "appointed-root-a",
    )
    custodian = _c1_external_ref(
        authority_module.ExternalAuthorityKind.PRODUCTION_DATA_CUSTODIAN,
        "appointed-custodian",
    )
    manifest_ref = record_ref(
        DigestDomain.PRODUCTION_MANIFEST,
        manifest_bytes,
        schema_version="polisyos.foundry.production-data-manifest.v1",
    )
    custody = authority_module.ProductionDataCustodyStatement(
        schema_version="polisyos.foundry.production-data-custody.v1",
        institutional_root=root_ref,
        appointed_custodian=custodian,
        manifest_ref=manifest_ref,
        access_mode="read_only",
        writer_access_disposition="denied",
    )
    custody_ref = authority_module.build_foundry_statement_ref(
        DigestDomain.PRODUCTION_CUSTODY,
        custody,
    )
    appointment_statement = authority_module.ProductionDataInputAppointmentStatement(
        schema_version="polisyos.foundry.production-data-appointment.v1",
        authority_purpose="n8_method_catalog_reconstruction",
        appointed_root=root_ref,
        manifest_relative_path="manifest.json",
        expected_manifest_ref=manifest_ref,
        appointed_custodian=custodian,
        custody_statement_ref=custody_ref,
        trust_policy_ref=_c1_ref(DigestDomain.TRUST_POLICY, "root-policy"),
    )
    authority_module.validate_appointment_custody_pair(
        appointment_statement,
        custody,
    )
    appointment_ref = authority_module.build_foundry_statement_ref(
        DigestDomain.PRODUCTION_APPOINTMENT,
        appointment_statement,
    )
    appointment = authority_module._mint_owner_capability(
        authority_module._PRODUCTION_APPOINTMENT_SPEC,
        authority_module._VerifiedProductionDataAppointmentPayload(
            appointment_binding_ref=_c1_ref(
                DigestDomain.SIGNED_RECORD_BINDING,
                "appointment-binding",
            ),
            custody_binding_ref=_c1_ref(
                DigestDomain.SIGNED_RECORD_BINDING,
                "custody-binding",
            ),
            appointment_ref=appointment_ref,
            custody_ref=custody_ref,
            appointment_statement=appointment_statement,
            custody_statement=custody,
        ),
    )
    root.chmod(0o555)
    return source, appointment, root, root_ref


def _resolve_candidate_root(
    *,
    source: authority_module.CanonicalFoundrySourceAuthority,
    appointment: authority_module.VerifiedProductionDataAppointment,
    requested_root: Path,
    resolver: object | None,
    attestor: object | None,
) -> object:
    with (
        authority_module._unwrap_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        ) as source_payload,
        authority_module._unwrap_owner_capability(
            appointment,
            authority_module._PRODUCTION_APPOINTMENT_SPEC,
        ) as appointment_payload,
    ):
        return authority_module.resolve_candidate_production_data_root_access(
            source_authority=source_payload,
            appointment=appointment_payload,
            requested_root=requested_root,
            request_ref=_c1_ref(DigestDomain.RESOLUTION_REQUEST, "root-request"),
            institutional_resolver=resolver,  # type: ignore[arg-type]
            root_access_attestor=attestor,  # type: ignore[arg-type]
        )


def _release_candidate_production_root(
    source: authority_module.CanonicalFoundrySourceAuthority,
    appointment: authority_module.VerifiedProductionDataAppointment,
    root: Path,
    result: object | None = None,
) -> None:
    if isinstance(result, authority_module.CandidateProductionDataRootAccess):
        authority_module._release_owner_capability(
            result.access,
            authority_module._ROOT_ACCESS_SPEC,
        )
        authority_module._release_owner_capability(
            result.mount,
            authority_module._PRODUCTION_MOUNT_SPEC,
        )
    authority_module._release_owner_capability(
        appointment,
        authority_module._PRODUCTION_APPOINTMENT_SPEC,
    )
    authority_module._release_owner_capability(
        source,
        authority_module._CANONICAL_SOURCE_SPEC,
    )
    if root.exists():
        root.chmod(0o755)


def test_authorized_external_read_only_data_root_passes_appointment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, appointment, root, root_ref = _candidate_production_root_fixture(
        monkeypatch,
        tmp_path,
    )
    result: object | None = None
    try:
        result = _resolve_candidate_root(
            source=source,
            appointment=appointment,
            requested_root=root,
            resolver=lambda observed: root_ref if observed == root else None,
            attestor=_c1_root_attestation,
        )
        assert isinstance(result, authority_module.CandidateProductionDataRootAccess)
        assert isinstance(result.mount, authority_module.ResolvedProductionDataMount)
        assert isinstance(result.access, authority_module.VerifiedProductionDataRootAccess)
        assert result.exact_manifest_bytes == (root / "manifest.json").read_bytes()
        assert "CandidateProductionDataRootAccess" not in repr(
            authority_module.MethodCatalogDependencyAuthorityResult
        )
    finally:
        _release_candidate_production_root(source, appointment, root, result)


def test_admitted_profile_round_trip_carries_root_access_refs_not_live_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, appointment, root, root_ref = _candidate_production_root_fixture(
        monkeypatch,
        tmp_path,
    )
    result: object | None = None
    receipt_raw: str | None = None
    access_ref: authority_module.FoundryRecordRef[
        Literal[DigestDomain.ROOT_ACCESS]
    ] | None = None
    binding_ref: authority_module.FoundryRecordRef[
        Literal[DigestDomain.SIGNED_RECORD_BINDING]
    ] | None = None
    try:
        result = _resolve_candidate_root(
            source=source,
            appointment=appointment,
            requested_root=root,
            resolver=lambda observed: root_ref if observed == root else None,
            attestor=_c1_root_attestation,
        )
        assert isinstance(result, authority_module.CandidateProductionDataRootAccess)
        with authority_module._unwrap_owner_capability(
            result.access,
            authority_module._ROOT_ACCESS_SPEC,
        ) as payload:
            access_ref = payload.attestation_ref
            binding_ref = payload.signed_binding_ref
        assert access_ref is not None
        assert binding_ref is not None
        fixture = _candidate_environment_fixture(
            tmp_path / "environment-receipt",
            _resolve_tracked_profile(),
            label="root-access-round-trip",
            sync_root_access_ref=access_ref,
            sync_root_access_binding_ref=binding_ref,
        )
        receipt_raw = fixture.receipt.model_dump_json()
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            authority_module.evidence_module.DependencyProfileEnvironmentStatement.model_validate(
                {
                    **fixture.receipt.statement.model_dump(mode="python"),
                    "live_root_access": result.access,
                },
                strict=True,
            )
    finally:
        _release_candidate_production_root(source, appointment, root, result)

    assert receipt_raw is not None
    reopened = DependencyProfileEnvironmentReceipt.model_validate_json(receipt_raw)
    assert reopened.statement.sync_root_access_ref == access_ref
    assert reopened.statement.sync_root_access_binding_ref == binding_ref
    authority_module.validate_no_owner_capability_in_persisted_schemas()


def test_fake_appointment_and_valid_read_only_root_is_not_established(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, appointment, root, _root_ref = _candidate_production_root_fixture(
        monkeypatch,
        tmp_path,
    )
    resolver_called = False
    try:
        with authority_module._unwrap_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        ) as source_payload:
            result = authority_module._unestablished_from_registry(
                source_payload,
                AuthorityPredicateId.PRODUCTION_APPOINTMENT,
            )
        assert result.failure_code is AuthorityFailureCode.APPOINTMENT_NOT_ESTABLISHED
        assert not resolver_called
    finally:
        _release_candidate_production_root(source, appointment, root)


def test_read_only_root_without_appointed_access_attestor_is_not_established(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, appointment, root, root_ref = _candidate_production_root_fixture(
        monkeypatch,
        tmp_path,
    )
    try:
        result = _resolve_candidate_root(
            source=source,
            appointment=appointment,
            requested_root=root,
            resolver=lambda _observed: root_ref,
            attestor=None,
        )
        assert isinstance(result, BidirectionalUnestablishedAuthorityPredicate)
        assert result.predicate_id is AuthorityPredicateId.ROOT_ACCESS
        assert result.failure_code is AuthorityFailureCode.ROOT_ACCESS_NOT_ESTABLISHED
    finally:
        _release_candidate_production_root(source, appointment, root)


def test_identical_copied_tree_without_institutional_root_evidence_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, appointment, root, _root_ref = _candidate_production_root_fixture(
        monkeypatch,
        tmp_path,
    )
    copied = tmp_path / "copied-production-data"
    shutil.copytree(root, copied)
    try:
        result = _resolve_candidate_root(
            source=source,
            appointment=appointment,
            requested_root=copied,
            resolver=lambda _observed: None,
            attestor=_c1_root_attestation,
        )
        assert isinstance(result, BidirectionalUnestablishedAuthorityPredicate)
        assert result.failure_code is AuthorityFailureCode.ROOT_ACCESS_NOT_ESTABLISHED
    finally:
        copied.chmod(0o755)
        _release_candidate_production_root(source, appointment, root)


def test_genuine_attestor_for_root_a_cannot_attest_requested_copy_b(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, appointment, root, _root_ref = _candidate_production_root_fixture(
        monkeypatch,
        tmp_path,
    )
    copied = tmp_path / "copy-b"
    shutil.copytree(root, copied)
    copied.chmod(0o555)
    root_b = _c1_external_ref(
        authority_module.ExternalAuthorityKind.INSTITUTIONAL_ROOT,
        "copied-root-b",
    )
    try:
        result = _resolve_candidate_root(
            source=source,
            appointment=appointment,
            requested_root=copied,
            resolver=lambda _observed: root_b,
            attestor=_c1_root_attestation,
        )
        assert isinstance(result, RejectedAuthorityPredicate)
        assert result.failure_code is AuthorityFailureCode.ROOT_ACCESS_MISMATCH
    finally:
        copied.chmod(0o755)
        _release_candidate_production_root(source, appointment, root)


def test_missing_mount_is_not_established_but_wrong_writable_or_moved_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, appointment, root, root_ref = _candidate_production_root_fixture(
        monkeypatch,
        tmp_path,
    )
    try:
        missing = _resolve_candidate_root(
            source=source,
            appointment=appointment,
            requested_root=tmp_path / "missing",
            resolver=lambda _observed: None,
            attestor=None,
        )
        assert isinstance(missing, BidirectionalUnestablishedAuthorityPredicate)
        assert missing.failure_code is AuthorityFailureCode.ROOT_ACCESS_NOT_ESTABLISHED

        root.chmod(0o755)
        writable = _resolve_candidate_root(
            source=source,
            appointment=appointment,
            requested_root=root,
            resolver=lambda _observed: root_ref,
            attestor=_c1_root_attestation,
        )
        assert isinstance(writable, RejectedAuthorityPredicate)
        assert writable.failure_code is AuthorityFailureCode.ROOT_ACCESS_MISMATCH
    finally:
        _release_candidate_production_root(source, appointment, root)


def test_writable_moved_or_unappointed_data_root_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, appointment, root, root_ref = _candidate_production_root_fixture(
        monkeypatch,
        tmp_path,
    )
    try:
        root.chmod(0o755)
        writable = _resolve_candidate_root(
            source=source,
            appointment=appointment,
            requested_root=root,
            resolver=lambda _observed: root_ref,
            attestor=_c1_root_attestation,
        )
        assert isinstance(writable, RejectedAuthorityPredicate)
        with authority_module._unwrap_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        ) as source_payload:
            unappointed = authority_module._unestablished_from_registry(
                source_payload,
                AuthorityPredicateId.PRODUCTION_APPOINTMENT,
            )
        assert unappointed.failure_code is AuthorityFailureCode.APPOINTMENT_NOT_ESTABLISHED
    finally:
        _release_candidate_production_root(source, appointment, root)


def test_manifest_and_attestor_consume_same_mount_and_detect_later_identity_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, appointment, root, root_ref = _candidate_production_root_fixture(
        monkeypatch,
        tmp_path,
    )

    def attest_then_change(
        challenge: authority_module.ProductionDataRootAccessChallenge,
    ) -> authority_module.RootAccessAttestationStatement:
        attestation = _c1_root_attestation(challenge)
        (root / "manifest.json").write_bytes(b'{"catalog":"changed-later"}\n')
        return attestation

    try:
        result = _resolve_candidate_root(
            source=source,
            appointment=appointment,
            requested_root=root,
            resolver=lambda _observed: root_ref,
            attestor=attest_then_change,
        )
        assert isinstance(result, RejectedAuthorityPredicate)
        assert result.failure_code is AuthorityFailureCode.ROOT_ACCESS_MISMATCH
    finally:
        _release_candidate_production_root(source, appointment, root)


def _candidate_source_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> authority_module.CanonicalFoundrySourceAuthority:
    _repo_root, _product_root, source_freeze = _install_clean_source_fixture(
        monkeypatch,
        tmp_path / "source-fixture",
    )
    source = authority_module._build_production_canonical_source_resolver().resolve(
        request=_authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(source, authority_module.CanonicalFoundrySourceAuthority)
    return source


def _release_candidate_source(
    source: authority_module.CanonicalFoundrySourceAuthority,
) -> None:
    authority_module._release_owner_capability(
        source,
        authority_module._CANONICAL_SOURCE_SPEC,
    )


def test_installed_source_binding_dag_joins_only_derived_refs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _candidate_source_fixture(monkeypatch, tmp_path)
    try:
        wheel_bytes = b"owner-retained-wheel-for-derived-binding"
        stable_ref = _c1_ref(DigestDomain.INSTALLED_STABLE, "derived-stable")
        selected_payload: dict[str, object] = {
            "artifact_kind": "wheel",
            "schema_version": "polisyos.foundry.selected-wheel.v1",
            "normalized_name": "policy-engine",
            "version": "0.1.0",
            "locked_source_ref": domain_digest(
                DigestDomain.LOCKED_SOURCE,
                b"derived-locked-source",
            ),
            "wheel_blob_ref": record_ref(
                DigestDomain.SELECTED_WHEEL,
                wheel_bytes,
                schema_version="polisyos.foundry.selected-wheel.v1",
            ),
            "wheel_record_manifest_ref": _c1_ref(
                DigestDomain.WHEEL_RECORD,
                "derived-record",
            ),
            "expected_stable_manifest_ref": stable_ref,
        }
        legacy_binding_ref = _c1_ref(
            DigestDomain.INSTALLED_BINDING,
            "arbitrary-fixture-binding",
        )
        selected_type = authority_module.evidence_module.SelectedWheelArtifactEvidence
        if "expected_source_binding_ref" in selected_type.model_fields:
            selected_payload["expected_source_binding_ref"] = legacy_binding_ref
        selected = selected_type.model_validate(selected_payload)

        with authority_module._unwrap_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        ) as source_payload:
            candidate = authority_module.recompute_candidate_installed_source_binding(
                source_authority=source_payload,
                selected_evidence=selected,
                observed_stable_manifest_ref=stable_ref,
                observed_artifact_bytes=wheel_bytes,
            )
        assert isinstance(candidate, authority_module.CandidateInstalledSourceBinding)
        derived_selected_ref = authority_module.build_foundry_statement_ref(
            DigestDomain.SELECTED_DISTRIBUTION,
            selected,
        )
        derived_binding_ref = authority_module.build_foundry_statement_ref(
            DigestDomain.INSTALLED_BINDING,
            candidate.statement,
        )
        assert candidate.statement.selected_evidence_ref == derived_selected_ref
        assert candidate.binding_ref == derived_binding_ref
        assert legacy_binding_ref != derived_binding_ref
        assert "expected_source_binding_ref" not in selected_type.model_fields, (
            "selected evidence still admits an arbitrary backward binding ref "
            f"{legacy_binding_ref.artifact_id} instead of the derived ref "
            f"{derived_binding_ref.artifact_id}"
        )

        joined = candidate.to_locked_distribution_identity(
            source_kind="registry",
            marker_expression=None,
        )
        assert joined == authority_module.evidence_module.LockedDistributionIdentity(
            normalized_name=selected.normalized_name,
            version=selected.version,
            source_kind="registry",
            selected_artifact_ref=derived_selected_ref,
            expected_stable_manifest_ref=stable_ref,
            expected_source_binding_ref=derived_binding_ref,
            marker_expression=None,
        )

        substituted_selected = replace(
            candidate,
            statement=candidate.statement.model_copy(
                update={
                    "selected_evidence_ref": _c1_ref(
                        DigestDomain.SELECTED_DISTRIBUTION,
                        "substituted-selected",
                    )
                }
            ),
        )
        with pytest.raises(ValueError, match="selected evidence ref"):
            substituted_selected.to_locked_distribution_identity(
                source_kind="registry",
                marker_expression=None,
            )

        substituted_binding = replace(
            candidate,
            binding_ref=_c1_ref(
                DigestDomain.INSTALLED_BINDING,
                "substituted-binding",
            ),
        )
        with pytest.raises(ValueError, match="installed binding ref"):
            substituted_binding.to_locked_distribution_identity(
                source_kind="registry",
                marker_expression=None,
            )
    finally:
        _release_candidate_source(source)


def test_substituted_wheel_with_consistently_rewritten_record_fails_lineage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _candidate_source_fixture(monkeypatch, tmp_path)
    try:
        expected_wheel = b"owner-retained-wheel"
        stable_ref = _c1_ref(DigestDomain.INSTALLED_STABLE, "stable-wheel")
        selected = authority_module.evidence_module.SelectedWheelArtifactEvidence(
            artifact_kind="wheel",
            schema_version="polisyos.foundry.selected-wheel.v1",
            normalized_name="policy-engine",
            version="0.1.0",
            locked_source_ref=domain_digest(
                DigestDomain.LOCKED_SOURCE,
                b"lock-selected-source",
            ),
            wheel_blob_ref=record_ref(
                DigestDomain.SELECTED_WHEEL,
                expected_wheel,
                schema_version="polisyos.foundry.selected-wheel.v1",
            ),
            wheel_record_manifest_ref=_c1_ref(DigestDomain.WHEEL_RECORD, "record"),
            expected_stable_manifest_ref=stable_ref,
        )
        with authority_module._unwrap_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        ) as source_payload:
            result = authority_module.recompute_candidate_installed_source_binding(
                source_authority=source_payload,
                selected_evidence=selected,
                observed_stable_manifest_ref=stable_ref,
                observed_artifact_bytes=b"substituted-wheel-with-rewritten-RECORD",
            )
        assert isinstance(result, RejectedAuthorityPredicate)
        assert result.predicate_id is AuthorityPredicateId.SELECTED_ARTIFACT
        assert result.failure_code is AuthorityFailureCode.ARTIFACT_MISMATCH
    finally:
        _release_candidate_source(source)


def test_source_first_runtime_files_bind_to_tracked_tree_not_tooling_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _candidate_source_fixture(monkeypatch, tmp_path)
    try:
        stable_ref = _c1_ref(DigestDomain.INSTALLED_STABLE, "source-first-stable")
        selected = authority_module.evidence_module.SelectedSourceTreeEvidence(
            artifact_kind="source_tree",
            schema_version="polisyos.foundry.selected-source-tree.v1",
            normalized_name="polisyos",
            version="0.1.0",
            locked_source_ref=domain_digest(
                DigestDomain.LOCKED_SOURCE,
                b"tracked-source",
            ),
            tracked_source_commit="1" * 40,
            source_tree_manifest_ref=_c1_ref(
                DigestDomain.SOURCE_TREE,
                "tracked-tree",
            ),
            expected_stable_manifest_ref=stable_ref,
        )
        monkeypatch.setenv("PYTHONPATH", "/tmp/ambient-tooling")
        with authority_module._unwrap_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        ) as source_payload:
            first = authority_module.recompute_candidate_installed_source_binding(
                source_authority=source_payload,
                selected_evidence=selected,
                observed_stable_manifest_ref=stable_ref,
            )
            monkeypatch.setenv("PYTHONPATH", "/tmp/different-tooling")
            second = authority_module.recompute_candidate_installed_source_binding(
                source_authority=source_payload,
                selected_evidence=selected,
                observed_stable_manifest_ref=stable_ref,
            )
        assert isinstance(first, authority_module.CandidateInstalledSourceBinding)
        assert isinstance(second, authority_module.CandidateInstalledSourceBinding)
        assert first == second
        assert first.statement.source_tree_ref == selected.source_tree_manifest_ref
        assert "environment" not in inspect.signature(
            authority_module.recompute_candidate_installed_source_binding
        ).parameters
    finally:
        _release_candidate_source(source)


def test_missing_build_lineage_is_exact_source_binding_not_established(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _candidate_source_fixture(monkeypatch, tmp_path)
    try:
        stable_ref = _c1_ref(DigestDomain.INSTALLED_STABLE, "built-stable")
        lineage_statement = authority_module.evidence_module.BuildLineageStatement(
            schema_version="polisyos.foundry.build-lineage.v1",
            source_artifact_ref=_c1_ref(DigestDomain.SELECTED_SOURCE, "source"),
            builder_toolchain_ref=_c1_ref(
                DigestDomain.TOOLCHAIN_RUNTIME,
                "builder",
            ),
            build_profile_ref=_c1_ref(DigestDomain.BUILD_PROFILE, "build-profile"),
            normalized_argv_hash=domain_digest(DigestDomain.BUILD_ARGV, b"argv"),
            build_environment_hash=domain_digest(
                DigestDomain.BUILD_ENVIRONMENT,
                b"environment",
            ),
            output_wheel_ref=_c1_ref(DigestDomain.SELECTED_WHEEL, "built-wheel"),
            verifier_provenance_ref=_c1_ref(
                DigestDomain.VERIFIER_PROVENANCE,
                "build-verifier",
            ),
            trust_resolution_receipt_ref=_c1_ref(
                DigestDomain.TRUST_RESOLUTION,
                "build-trust",
            ),
        )
        lineage = authority_module.evidence_module.PersistedBuildLineageEvidence(
            record_ref=authority_module.build_foundry_statement_ref(
                DigestDomain.BUILD_LINEAGE,
                lineage_statement,
            ),
            statement=lineage_statement,
            signed_binding_ref=_c1_ref(
                DigestDomain.SIGNED_RECORD_BINDING,
                "build-binding",
            ),
        )
        selected = authority_module.evidence_module.SelectedBuiltArtifactEvidence(
            artifact_kind="built_source",
            schema_version="polisyos.foundry.selected-built-wheel.v1",
            normalized_name="built-package",
            version="1.0",
            locked_source_ref=domain_digest(
                DigestDomain.LOCKED_SOURCE,
                b"built-lock",
            ),
            source_blob_ref=lineage_statement.source_artifact_ref,
            build_lineage=lineage,
            output_wheel_ref=lineage_statement.output_wheel_ref,
            expected_stable_manifest_ref=stable_ref,
        )
        with authority_module._unwrap_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        ) as source_payload:
            result = authority_module.recompute_candidate_installed_source_binding(
                source_authority=source_payload,
                selected_evidence=selected,
                observed_stable_manifest_ref=stable_ref,
                resolved_build_lineage=None,
            )
        assert isinstance(result, BidirectionalUnestablishedAuthorityPredicate)
        assert result.predicate_id is AuthorityPredicateId.INSTALLED_SOURCE
        assert result.failure_code is AuthorityFailureCode.SOURCE_BINDING_NOT_ESTABLISHED
        assert result.missing_domains == (DigestDomain.INSTALLED_BINDING,)
    finally:
        _release_candidate_source(source)


def test_every_owner_entrypoint_maps_mapping_or_nested_fake_to_its_exact_result_union(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _candidate_source_fixture(monkeypatch, tmp_path)
    try:
        with authority_module._unwrap_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        ) as source_payload:
            synthetic_owner = type("_SyntheticOwner", (), {})()
            synthetic_owner._source_authority = source_payload
            signature = inspect.Signature(
                [inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
            )
            bound = signature.bind(synthetic_owner)
            observed = 0
            for entrypoint in authority_module._OWNER_ENTRYPOINT_SPECS:
                target = entrypoint.target
                function = (
                    target.concrete_owner_type.__dict__[target.method_name]
                    if isinstance(target, authority_module.OwnerMethodTarget)
                    else getattr(authority_module, target.function_name)
                )
                assert getattr(function, "__gy_n12_owner_guard__", None) is entrypoint
                if not entrypoint.fault_policies:
                    continue
                hints = authority_module.get_type_hints(function, include_extras=True)
                return_members = tuple(
                    authority_module._walk_annotation(hints["return"])
                )
                assert BidirectionalUnestablishedAuthorityPredicate in return_members
                for policy in entrypoint.fault_policies:
                    result = authority_module._owner_fault_result(
                        authority_module.OwnerCapabilityFault(
                            code=authority_module.OwnerCapabilityFaultCode.UNMINTED_TOKEN,
                            disposition=(
                                authority_module.OwnerCapabilityFaultDisposition.REJECTED
                            ),
                            capability_kind=policy.capability_kind,
                            payload_path=("nested", "fake"),
                        ),
                        bound,
                        entrypoint,
                    )
                    assert isinstance(
                        result,
                        BidirectionalUnestablishedAuthorityPredicate,
                    )
                    assert result.predicate_id is policy.predicate_id
                    assert result.failure_code is policy.not_established_code
                    observed += 1
            assert observed == sum(
                len(row.fault_policies)
                for row in authority_module._OWNER_ENTRYPOINT_SPECS
            )
    finally:
        _release_candidate_source(source)


def test_two_fake_parameters_map_to_distinct_predicates_and_typed_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _candidate_source_fixture(monkeypatch, tmp_path)
    record_token, binding_ref = _mint_test_signed_record(
        DigestDomain.PRODUCTION_APPOINTMENT,
        b"appointment",
    )
    graph = _mint_test_signed_graph(
        ((DigestDomain.PRODUCTION_APPOINTMENT, record_token, binding_ref),)
    )
    capsule, _index, _bindings = _c1_capsule_graph()
    try:
        with authority_module._unwrap_owner_capability(
            source,
            authority_module._CANONICAL_SOURCE_SPEC,
        ) as source_payload:
            authority = authority_module._ProductionDataAppointmentAuthority(
                source_authority=source_payload
            )
            source_fake = authority.resolve(
                source_authority=object(),  # type: ignore[arg-type]
                capsule=capsule,
                signed_graph=graph,
            )
            graph_fake = authority.resolve(
                source_authority=source,
                capsule=capsule,
                signed_graph=object(),  # type: ignore[arg-type]
            )
        assert isinstance(source_fake, BidirectionalUnestablishedAuthorityPredicate)
        assert isinstance(graph_fake, BidirectionalUnestablishedAuthorityPredicate)
        assert source_fake.predicate_id is AuthorityPredicateId.SOURCE_FREEZE
        assert source_fake.failure_code is AuthorityFailureCode.SOURCE_NOT_ESTABLISHED
        assert graph_fake.predicate_id is AuthorityPredicateId.TRUST_SIGNATURE
        assert graph_fake.failure_code is AuthorityFailureCode.TRUST_NOT_ESTABLISHED
    finally:
        authority_module._release_owner_capability(
            graph,
            authority_module._SIGNED_GRAPH_SPEC,
        )
        authority_module._release_owner_capability(
            record_token,
            authority_module._SIGNED_RECORD_SPEC,
        )
        _release_candidate_source(source)


def _tracked_owner_declaration(
    *,
    profile_id: str,
    extras: tuple[str, ...],
) -> MethodCatalogDependencyProfileDeclaration:
    """Build one scratch owner row from the current tracked TOML and lock bytes."""

    registry_wire = tomllib.loads(_PROFILE_REGISTRY.read_text(encoding="utf-8"))
    pyproject_bytes = (_PRODUCT_ROOT / "pyproject.toml").read_bytes()
    lockfile_bytes = (_PRODUCT_ROOT / "uv.lock").read_bytes()
    pyproject_wire = tomllib.loads(pyproject_bytes.decode("utf-8"))
    lock_wire = tomllib.loads(lockfile_bytes.decode("utf-8"))
    owner_row = registry_wire["declarations"][0]

    assert tuple(sorted(extras)) == extras
    assert set(extras).issubset(pyproject_wire["project"]["optional-dependencies"])
    assert any(row["name"] == owner_row["root_distribution"] for row in lock_wire["package"])
    return MethodCatalogDependencyProfileDeclaration(
        schema_version=owner_row["schema_version"],
        profile_id=profile_id,
        root_distribution=owner_row["root_distribution"],
        extras=extras,
        python_constraint=owner_row["python_constraint"],
        resolver_name=owner_row["resolver_name"],
        resolver_version=owner_row["resolver_version"],
        pyproject_ref=domain_digest(DigestDomain.PYPROJECT, pyproject_bytes),
        lockfile_ref=domain_digest(DigestDomain.UV_LOCK, lockfile_bytes),
    )


def _resolve_dependency_discriminant_from_owner_data(
    declaration: MethodCatalogDependencyProfileDeclaration,
    *,
    lockfile_bytes: bytes | None = None,
) -> object:
    """Resolve the dependency-only candidate through the required Foundry seam."""

    resolver = getattr(profile_module, "resolve_dependency_discriminant", None)
    assert callable(resolver), (
        "missing behavior: Foundry must resolve a dependency-only discriminant from owner data"
    )
    return resolver(
        declaration,
        pyproject_bytes=(_PRODUCT_ROOT / "pyproject.toml").read_bytes(),
        lockfile_bytes=lockfile_bytes or (_PRODUCT_ROOT / "uv.lock").read_bytes(),
        marker_environment=_marker_environment(),
    )


def _resolve_dependency_profile_from_owner_data(
    declaration: MethodCatalogDependencyProfileDeclaration,
    *,
    lockfile_bytes: bytes | None = None,
) -> ResolvedMethodCatalogDependencyProfile:
    """Resolve a candidate profile solely to produce an existing receipt fixture."""

    result = resolve_dependency_profile(
        declaration,
        pyproject_bytes=(_PRODUCT_ROOT / "pyproject.toml").read_bytes(),
        lockfile_bytes=lockfile_bytes or (_PRODUCT_ROOT / "uv.lock").read_bytes(),
        marker_environment=_marker_environment(),
        production_data_manifest=ProductionDataManifestPresent(
            kind="present",
            exact_bytes=b"{}",
        ),
        admission=_admission(declaration),
    )
    assert isinstance(result, ResolvedMethodCatalogDependencyProfile)
    return result


def _matching_dependency_observations(discriminant: object) -> tuple[dict[str, str], ...]:
    """Project only the resolved closure into generic installed coordinates."""

    rows = getattr(discriminant, "distributions", None)
    assert isinstance(rows, tuple) and rows, (
        "missing behavior: dependency discriminant must retain the resolved distribution closure"
    )
    return tuple(
        {
            "name": row.name,
            "version": row.version,
        }
        for row in rows
    )


def _diagnose_dependency_environment(
    discriminant: object,
    observations: tuple[dict[str, str], ...],
) -> object:
    """Run the non-authoritative generic comparison required by GY-DEF22."""

    diagnoser = getattr(profile_module, "diagnose_dependency_environment", None)
    assert callable(diagnoser), (
        "missing behavior: Foundry must diagnose installed coordinates against the discriminant"
    )
    return diagnoser(
        discriminant=discriminant,
        observed_distributions={
            "observation_kind": "ambient",
            "distributions": observations,
        },
    )


def _diagnose_receipt_backed_dependency_environment(
    discriminant: object,
    fixture: _CandidateEnvironmentFixture,
) -> object:
    """Resolve a candidate Foundry receipt before comparing source identity."""

    diagnoser = getattr(profile_module, "diagnose_dependency_environment", None)
    assert callable(diagnoser)
    return diagnoser(
        discriminant=discriminant,
        observed_distributions={
            "observation_kind": "foundry_environment_receipt",
            "environment_receipt": fixture.receipt,
        },
        environment_root=fixture.root,
        evidence=fixture.evidence,
    )


def _diagnostic_coordinate(result: object) -> str | None:
    """Read the first ordered diagnostic coordinate without assuming its DTO class."""

    first_case = getattr(result, "first_case", None)
    return getattr(first_case, "coordinate", None)


def _assert_dependency_diagnostic_failure(
    discriminant: object,
    observations: tuple[dict[str, str], ...],
) -> object:
    """Assert the public diagnostic detects one real dependency disagreement."""

    result = _diagnose_dependency_environment(discriminant, observations)
    assert getattr(result, "status", None) == "fail", (
        "dependency disagreement was not detected"
    )
    return result


def test_forged_ambient_source_and_artifact_mapping_is_not_established() -> None:
    declaration = _tracked_owner_declaration(
        profile_id="forged-ambient-source",
        extras=("research",),
    )
    discriminant = _resolve_dependency_discriminant_from_owner_data(declaration)
    forged = tuple(
        {
            "name": row.name,
            "version": row.version,
            "source_kind": row.source_kind,
            "selected_artifact": row.selected_artifact,
            "selected_artifact_predicate_class": "independently_reconciled",
        }
        for row in discriminant.distributions
    )

    legacy_result = profile_module.diagnose_dependency_environment(
        discriminant=discriminant,
        observed_distributions=forged,
    )
    discriminated_result = profile_module.diagnose_dependency_environment(
        discriminant=discriminant,
        observed_distributions={
            "observation_kind": "ambient",
            "distributions": forged,
        },
    )

    assert legacy_result.status == "not_established"
    assert legacy_result.predicate_class == "not_established"
    assert discriminated_result.status == "not_established"
    assert discriminated_result.predicate_class == "not_established"


def test_source_and_artifact_diagnostic_requires_reconciled_foundry_receipt(
    tmp_path: Path,
) -> None:
    profile = _resolve_tracked_profile()
    discriminant = _resolve_dependency_discriminant_from_owner_data(profile.declaration)
    fixture = _candidate_environment_fixture(
        tmp_path,
        profile,
        label="receipt-backed-diagnostic",
    )
    target = profile.distributions[0]
    mismatch_fixture = _candidate_environment_fixture(
        tmp_path,
        profile,
        label="receipt-backed-source-mismatch",
        selected_overrides={
            target.name: (
                target.version,
                domain_digest(
                    DigestDomain.SELECTED_DISTRIBUTION,
                    b"receipt-backed-selected-artifact-mismatch",
                ),
            )
        },
    )

    unresolved = profile_module.diagnose_dependency_environment(
        discriminant=discriminant,
        observed_distributions={
            "observation_kind": "foundry_environment_receipt",
            "environment_receipt": fixture.receipt,
        },
    )
    result = profile_module.diagnose_dependency_environment(
        discriminant=discriminant,
        observed_distributions={
            "observation_kind": "foundry_environment_receipt",
            "environment_receipt": fixture.receipt,
        },
        environment_root=fixture.root,
        evidence=fixture.evidence,
    )
    mismatch = _diagnose_receipt_backed_dependency_environment(
        discriminant,
        mismatch_fixture,
    )
    marker_path = (
        fixture.root
        / ".polisyos-foundry-authority-v1"
        / "environment-marker.json"
    )
    marker_path.write_bytes(b"corrupt retained marker")
    corrupt = profile_module.diagnose_dependency_environment(
        discriminant=discriminant,
        observed_distributions={
            "observation_kind": "foundry_environment_receipt",
            "environment_receipt": fixture.receipt,
        },
        environment_root=fixture.root,
        evidence=fixture.evidence,
    )

    assert unresolved.status == "not_established"
    assert unresolved.predicate_class == "not_established"
    assert result.status == "pass"
    assert result.predicate_class == "recomputed"
    assert mismatch.status == "fail"
    assert mismatch.predicate_class == "recomputed"
    assert mismatch.first_case.coordinate == (
        f"distribution:{target.name}:selected_artifact"
    )
    assert corrupt.status == "not_established"
    assert corrupt.predicate_class == "not_established"


def test_public_diagnostic_distinguishes_unusable_evidence_from_zero_cases(
    tmp_path: Path,
) -> None:
    profile = _resolve_tracked_profile()
    discriminant = _resolve_dependency_discriminant_from_owner_data(profile.declaration)
    fixture = _candidate_environment_fixture(
        tmp_path,
        profile,
        label="public-diagnostic-outcome",
    )
    forged = tuple(
        {
            "name": row.name,
            "version": row.version,
            "source_kind": row.source_kind,
            "selected_artifact": row.selected_artifact,
            "selected_artifact_predicate_class": "independently_reconciled",
        }
        for row in discriminant.distributions
    )

    forged_result = profile_module.diagnose_dependency_environment(
        discriminant=discriminant,
        observed_distributions=forged,
    )
    unresolved_result = profile_module.diagnose_dependency_environment(
        discriminant=discriminant,
        observed_distributions={
            "observation_kind": "foundry_environment_receipt",
            "environment_receipt": fixture.receipt,
        },
    )
    matching_result = _diagnose_receipt_backed_dependency_environment(
        discriminant,
        fixture,
    )

    assert not hasattr(profile_module, "compare_dependency_distributions")
    assert not hasattr(profile_module, "_compare_dependency_distributions")
    assert forged_result.status == "not_established"
    assert unresolved_result.status == "not_established"
    assert matching_result.status == "pass"
    assert matching_result.ordered_cases == ()


def _actual_consumer_governing_bytes(diagnostic_verification: object | None) -> tuple[bytes, ...]:
    """Run N8, N10a, and chronology against one companion and retain only governing bytes."""

    producer = getattr(n8, "build_dependency_discriminant_companion", None)
    n8_consumer = getattr(n8, "validate_foundry_dependency_discriminant", None)
    n10a_consumer = getattr(n10a, "read_foundry_dependency_discriminant", None)
    chronology_consumer = getattr(chronology, "read_foundry_dependency_discriminant", None)
    assert callable(producer), (
        "missing behavior: N8 must produce the shared Foundry dependency discriminant"
    )
    assert callable(n8_consumer), (
        "missing behavior: N8 must consume the shared Foundry dependency discriminant"
    )
    assert callable(n10a_consumer), (
        "missing behavior: N10a must consume the shared Foundry dependency discriminant"
    )
    assert callable(chronology_consumer), (
        "missing behavior: chronology must consume the shared Foundry dependency discriminant"
    )
    repo_root = n8._repo_root()
    source_freeze = _git_at(repo_root, "log", "-1", "--format=%H", "--", n8.OUTPUT_PATH)
    assert len(source_freeze) == 40
    companion = producer(repo_root=repo_root, source_freeze=source_freeze)
    results = (
        n8_consumer(
            repo_root=repo_root,
            companion=companion,
            diagnostic_verification=diagnostic_verification,
        ),
        n10a_consumer(
            repo_root=repo_root,
            companion=companion,
            diagnostic_verification=diagnostic_verification,
        ),
        chronology_consumer(
            repo_root=repo_root,
            companion=companion,
            diagnostic_verification=diagnostic_verification,
        ),
    )
    governing = tuple(getattr(result, "governing_result", None) for result in results)
    assert all(value is not None for value in governing), (
        "missing behavior: each consumer must expose governing output separately"
    )
    return tuple(canonical_json_bytes(value) for value in governing)


def _scratch_profile_registry(
    tmp_path: Path,
    *,
    profile_id: str,
    extras: tuple[str, ...],
) -> Path:
    """Append one owner-owned declaration whose digests come from tracked bytes."""

    declaration = _tracked_owner_declaration(profile_id=profile_id, extras=extras)
    registry = tmp_path / "method_catalog_dependency_profiles.toml"
    registry.write_text(
        _PROFILE_REGISTRY.read_text(encoding="utf-8")
        + "\n[[declarations]]\n"
        + f'schema_version = "{declaration.schema_version}"\n'
        + f'profile_id = "{declaration.profile_id}"\n'
        + f'root_distribution = "{declaration.root_distribution}"\n'
        + "extras = ["
        + ", ".join(f'\"{extra}\"' for extra in declaration.extras)
        + "]\n"
        + f'python_constraint = "{declaration.python_constraint}"\n'
        + f'resolver_name = "{declaration.resolver_name}"\n'
        + f'resolver_version = "{declaration.resolver_version}"\n'
        + f'pyproject_sha256 = "{declaration.pyproject_ref.value}"\n'
        + f'uv_lock_sha256 = "{declaration.lockfile_ref.value}"\n',
        encoding="utf-8",
    )
    return registry


def test_cb_i02_research_profile_names_torch_as_first_generic_case(
    tmp_path: Path,
) -> None:
    research = _tracked_owner_declaration(profile_id="research", extras=("research",))
    discriminant = _resolve_dependency_discriminant_from_owner_data(research)
    profile = _resolve_dependency_profile_from_owner_data(research)
    torch = next(row for row in discriminant.distributions if row.name == "torch")
    assert torch.version == "2.10.0"
    fixture = _candidate_environment_fixture(
        tmp_path,
        profile,
        label="research-source-mismatch",
        selected_overrides={
            "torch": (
                torch.version,
                domain_digest(
                    DigestDomain.SELECTED_DISTRIBUTION,
                    b"different-receipt-backed-torch-source",
                ),
            )
        },
    )

    result = _diagnose_receipt_backed_dependency_environment(discriminant, fixture)

    assert getattr(result, "status", None) == "fail"
    assert _diagnostic_coordinate(result) is not None
    assert _diagnostic_coordinate(result).startswith("distribution:torch:")
    governing_without_diagnostic = _actual_consumer_governing_bytes(None)
    governing_with_diagnostic = _actual_consumer_governing_bytes(result)
    assert governing_with_diagnostic == governing_without_diagnostic


def test_cb_i02a_label_and_shape_cannot_mask_two_data_generated_incompatibilities(
    tmp_path: Path,
) -> None:
    research = _tracked_owner_declaration(profile_id="same-label", extras=("research",))
    baseline = _resolve_dependency_discriminant_from_owner_data(research)
    baseline_profile = _resolve_dependency_profile_from_owner_data(research)
    fixture = _candidate_environment_fixture(
        tmp_path,
        baseline_profile,
        label="same-label-baseline",
    )
    lockfile_bytes = (_PRODUCT_ROOT / "uv.lock").read_bytes()
    target = next(row for row in baseline.distributions if row.name == "torch")
    needle = f'name = "{target.name}"\nversion = "{target.version}"'.encode()
    assert lockfile_bytes.count(needle) == 1
    mutated_lock = lockfile_bytes.replace(
        needle,
        f'name = "{target.name}"\nversion = "9999.0"'.encode(),
        1,
    )
    same_label = research.model_copy(
        update={"lockfile_ref": domain_digest(DigestDomain.UV_LOCK, mutated_lock)}
    )
    mutated = _resolve_dependency_discriminant_from_owner_data(
        same_label,
        lockfile_bytes=mutated_lock,
    )
    mutated_result = _diagnose_receipt_backed_dependency_environment(mutated, fixture)

    registry = _scratch_profile_registry(
        tmp_path,
        profile_id="zz-second-data-generated-profile",
        extras=("test",),
    )
    second_profile = resolve_profile_declaration(
        load_dependency_profile_registry(registry),
        profile_id="zz-second-data-generated-profile",
    )
    second = _resolve_dependency_discriminant_from_owner_data(second_profile)
    second_result = _diagnose_receipt_backed_dependency_environment(second, fixture)

    assert getattr(mutated_result, "status", None) == "fail"
    assert getattr(second_result, "status", None) == "fail"
    assert (
        _diagnostic_coordinate(mutated_result)
        == f"distribution:{target.name}:selected_artifact"
    )
    second_names = {row.name for row in baseline.distributions}
    second_missing = sorted(
        row.name for row in second.distributions if row.name not in second_names
    )
    assert second_missing
    assert _diagnostic_coordinate(second_result) == f"distribution:{second_missing[0]}:missing"
    governing_without_diagnostic = _actual_consumer_governing_bytes(None)
    assert _actual_consumer_governing_bytes(mutated_result) == governing_without_diagnostic
    assert _actual_consumer_governing_bytes(second_result) == governing_without_diagnostic
    assert research.profile_id == same_label.profile_id


def test_cb_i03_outside_closure_difference_is_diagnostic_irrelevant(
    tmp_path: Path,
) -> None:
    declaration = _tracked_owner_declaration(profile_id="irrelevant-extra", extras=("research",))
    discriminant = _resolve_dependency_discriminant_from_owner_data(declaration)
    profile = _resolve_dependency_profile_from_owner_data(declaration)
    baseline_fixture = _candidate_environment_fixture(
        tmp_path,
        profile,
        label="inside-selected-closure",
    )
    outside = authority_module.evidence_module.InstalledDistributionIdentity(
        normalized_name="outside-selected-closure",
        version="1.0.0",
        selected_artifact_ref=_c1_ref(
            DigestDomain.SELECTED_DISTRIBUTION,
            "outside:selected",
        ),
        observed_stable_manifest_ref=_c1_ref(
            DigestDomain.INSTALLED_STABLE,
            "outside:stable",
        ),
        observed_instance_manifest_ref=_c1_ref(
            DigestDomain.INSTALLED_INSTANCE,
            "outside:instance",
        ),
        observed_source_binding_ref=_c1_ref(
            DigestDomain.INSTALLED_BINDING,
            "outside:binding",
        ),
    )
    extra_fixture = _candidate_environment_fixture(
        tmp_path,
        profile,
        label="outside-selected-closure",
        extra_distributions=(outside,),
    )

    baseline = _diagnose_receipt_backed_dependency_environment(
        discriminant,
        baseline_fixture,
    )
    observed = _diagnose_receipt_backed_dependency_environment(
        discriminant,
        extra_fixture,
    )

    assert getattr(baseline, "status", None) == getattr(observed, "status", None) == "pass"
    assert _diagnostic_coordinate(baseline) == _diagnostic_coordinate(observed) is None


def test_cb_i03a_novel_admitted_profile_verifies_from_owner_data(tmp_path: Path) -> None:
    registry = _scratch_profile_registry(
        tmp_path,
        profile_id="zz-novel-admitted-profile",
        extras=("test",),
    )
    declaration = resolve_profile_declaration(
        load_dependency_profile_registry(registry),
        profile_id="zz-novel-admitted-profile",
    )
    discriminant = _resolve_dependency_discriminant_from_owner_data(declaration)
    profile = _resolve_dependency_profile_from_owner_data(declaration)
    fixture = _candidate_environment_fixture(
        tmp_path,
        profile,
        label="novel-admitted-profile",
    )

    result = _diagnose_receipt_backed_dependency_environment(
        discriminant,
        fixture,
    )

    assert getattr(result, "status", None) == "pass"
    assert _diagnostic_coordinate(result) is None


def test_p29_distribution_comparison_cannot_be_replaced_by_schema_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    research = _tracked_owner_declaration(profile_id="p29-research", extras=("research",))
    discriminant = _resolve_dependency_discriminant_from_owner_data(research)
    observations = list(_matching_dependency_observations(discriminant))
    next(row for row in observations if row["name"] == "torch")["version"] = "9999.0"
    calculator = getattr(
        profile_module,
        "_calculate_dependency_distribution_cases",
        None,
    )
    assert callable(calculator), (
        "missing behavior: diagnostic verification must execute generic distribution comparison"
    )
    baseline = _assert_dependency_diagnostic_failure(
        discriminant,
        tuple(observations),
    )
    calls = 0

    def property_removed(**_kwargs: object) -> tuple[()]:
        nonlocal calls
        calls += 1
        return ()

    monkeypatch.setattr(
        profile_module,
        "_calculate_dependency_distribution_cases",
        property_removed,
    )

    with pytest.raises(AssertionError, match="dependency disagreement was not detected"):
        _assert_dependency_diagnostic_failure(discriminant, tuple(observations))

    assert getattr(baseline, "status", None) == "fail"
    assert calls == 1, "public diagnostic must invoke one canonical case calculation"


def test_p33_profile_labels_cannot_override_recomputed_closure_content(tmp_path: Path) -> None:
    first = _tracked_owner_declaration(profile_id="label-one", extras=("research",))
    renamed = _tracked_owner_declaration(profile_id="label-two", extras=("research",))
    first_discriminant = _resolve_dependency_discriminant_from_owner_data(first)
    first_profile = _resolve_dependency_profile_from_owner_data(first)
    fixture = _candidate_environment_fixture(
        tmp_path,
        first_profile,
        label="label-independent-receipt",
    )
    renamed_result = _diagnose_receipt_backed_dependency_environment(
        _resolve_dependency_discriminant_from_owner_data(renamed),
        fixture,
    )
    registry = _scratch_profile_registry(
        tmp_path,
        profile_id="zz-label-independent-profile",
        extras=("test",),
    )
    second = resolve_profile_declaration(
        load_dependency_profile_registry(registry),
        profile_id="zz-label-independent-profile",
    )
    second_result = _diagnose_receipt_backed_dependency_environment(
        _resolve_dependency_discriminant_from_owner_data(second),
        fixture,
    )

    assert getattr(renamed_result, "status", None) == "pass"
    assert getattr(second_result, "status", None) == "fail"
