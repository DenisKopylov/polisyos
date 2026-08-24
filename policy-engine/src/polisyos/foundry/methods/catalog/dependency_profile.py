"""Pure candidate reducers for Foundry dependency-profile identity.

These reducers construct content-bound candidate evidence only.  The production
authority path in :mod:`dependency_authority` currently refuses before it can
admit or persist any value produced here.
"""

from __future__ import annotations

import tomllib
from collections import deque
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal, Protocol

from packaging.markers import Marker
from packaging.utils import canonicalize_name
from pydantic import Field, model_validator

from polisyos.foundry.methods.catalog.dependency_evidence import (
    AuthorityFailureCode,
    AuthorityPredicateFailure,
    AuthorityPredicateId,
    DependencyEnvironmentMarkerStatement,
    DependencyProfileEnvironmentStatement,
    DigestDomain,
    DigestPredicateMismatch,
    DomainDigest,
    DomainScalar,
    EnvironmentKeyText,
    EnvironmentValueText,
    FoundryAuthorityModel,
    FoundryRecordRef,
    IdentityText,
    MissingPredicateEvidence,
    ProductionDataManifestInput,
    ProductionDataManifestMissingFailure,
    ProductionDataManifestPresent,
    ProductionDataManifestUnavailable,
    ScalarDomain,
    ScalarPredicateMismatch,
    canonical_json_bytes,
    domain_digest,
    record_ref,
)


class MethodCatalogDependencyProfileDeclaration(FoundryAuthorityModel):
    """Data-owned selection of the root distribution and resolver inputs."""

    schema_version: Literal["polisyos.foundry.dependency-profile.v1"]
    profile_id: IdentityText
    root_distribution: IdentityText
    extras: tuple[IdentityText, ...]
    python_constraint: IdentityText
    resolver_name: Literal["uv"]
    resolver_version: Literal["0.9.21"]
    pyproject_ref: DomainDigest[Literal[DigestDomain.PYPROJECT]]
    lockfile_ref: DomainDigest[Literal[DigestDomain.UV_LOCK]]

    @model_validator(mode="after")
    def validate_selection(self) -> MethodCatalogDependencyProfileDeclaration:
        if tuple(sorted(set(self.extras))) != self.extras:
            raise ValueError("profile extras must be sorted and unique")
        return self


class DependencyProfileRegistryStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.dependency-profile-registry.v1"]
    declarations: tuple[MethodCatalogDependencyProfileDeclaration, ...]

    @model_validator(mode="after")
    def validate_unique_profiles(self) -> DependencyProfileRegistryStatement:
        ids = tuple(row.profile_id for row in self.declarations)
        if not ids or len(ids) != len(set(ids)) or tuple(sorted(ids)) != ids:
            raise ValueError("dependency profiles must be non-empty, sorted and unique")
        return self


class MethodCatalogProfileAdmission(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.profile-admission.v1"]
    authority_purpose: Literal["n8_method_catalog_reconstruction"]
    profile_id: IdentityText
    declaration_ref: FoundryRecordRef[Literal[DigestDomain.PROFILE_DECLARATION]]
    python_runtime_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    uv_executable_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_EXECUTABLE]
    ]
    production_data_trust_policy_ref: FoundryRecordRef[
        Literal[DigestDomain.TRUST_POLICY]
    ]
    predicate_class: Literal["recomputed"]


class LockedDistributionIdentity(FoundryAuthorityModel):
    """One selected lock member, bound to its complete lock row."""

    name: IdentityText
    version: IdentityText
    source_kind: IdentityText
    selected_artifact: DomainDigest[Literal[DigestDomain.SELECTED_DISTRIBUTION]]


def read_candidate_production_data_manifest(
    production_data_root: Path,
) -> ProductionDataManifestInput:
    """Classify the native manifest input without claiming root authority.

    This candidate/reference reader is intentionally unreachable from the
    cutoff-first production authority.  It preserves missing versus unreadable
    as evidence while both map to the one public not-established predicate.
    """

    manifest_path = production_data_root / "manifest.json"
    try:
        exact_bytes = manifest_path.read_bytes()
    except FileNotFoundError:
        return ProductionDataManifestUnavailable(kind="unavailable", cause="missing")
    except OSError:
        return ProductionDataManifestUnavailable(kind="unavailable", cause="unreadable")
    return ProductionDataManifestPresent(kind="present", exact_bytes=exact_bytes)


class DependencyProfileInputMismatch(FoundryAuthorityModel):
    kind: Literal["dependency_profile_input_mismatch"]
    predicate_id: Literal[AuthorityPredicateId.PURPOSE_PROFILE]
    code: Literal[AuthorityFailureCode.PROFILE_MISMATCH]
    field: Literal[
        "profile_admission",
        "pyproject_ref",
        "lockfile_ref",
        "root_distribution",
        "selected_lock_graph",
    ]
    expected: IdentityText
    observed: IdentityText
    predicate_class: Literal["recomputed"]


DependencyProfileCandidateFailure = Annotated[
    ProductionDataManifestMissingFailure
    | DependencyProfileInputMismatch
    | DigestPredicateMismatch
    | ScalarPredicateMismatch,
    Field(discriminator="kind"),
]


class ResolvedMethodCatalogDependencyProfile(FoundryAuthorityModel):
    """Pure, non-authoritative candidate closure derived from tracked inputs."""

    status: Literal["resolved"]
    admission: MethodCatalogProfileAdmission
    declaration: MethodCatalogDependencyProfileDeclaration
    marker_environment: tuple[tuple[EnvironmentKeyText, EnvironmentValueText], ...]
    distributions: tuple[LockedDistributionIdentity, ...]
    distribution_set: DomainDigest[Literal[DigestDomain.DISTRIBUTION_SET]]
    stable_content_set: DomainDigest[Literal[DigestDomain.CONTENT_SET_STABLE]]
    stable_closure: DomainDigest[Literal[DigestDomain.DEPENDENCY_CLOSURE]]
    production_data_manifest_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_MANIFEST]]


class ObservedInstalledDistribution(FoundryAuthorityModel):
    name: IdentityText
    version: IdentityText
    selected_artifact: DomainDigest[Literal[DigestDomain.SELECTED_DISTRIBUTION]]


class DependencyProfileEnvironmentReceipt(FoundryAuthorityModel):
    """Candidate instance evidence; it is not writer-independent custody."""

    receipt_ref: FoundryRecordRef[Literal[DigestDomain.ENVIRONMENT_RECEIPT]]
    statement: DependencyProfileEnvironmentStatement
    predicate_class: Literal["recomputed"]

    @model_validator(mode="after")
    def validate_content_binding(self) -> DependencyProfileEnvironmentReceipt:
        expected = record_ref(
            DigestDomain.ENVIRONMENT_RECEIPT,
            canonical_json_bytes(self.statement.model_dump(mode="json")),
            schema_version=self.statement.schema_version,
        )
        if self.receipt_ref != expected:
            raise ValueError("environment receipt is not content-bound")
        return self


class DependencyProfileReconciliationPass(FoundryAuthorityModel):
    status: Literal["pass"]
    profile_id: IdentityText
    stable_closure: DomainDigest[Literal[DigestDomain.DEPENDENCY_CLOSURE]]
    environment_receipt_ref: FoundryRecordRef[Literal[DigestDomain.ENVIRONMENT_RECEIPT]]
    predicate_class: Literal["independently_reconciled"]


class DependencyProfileReconciliationFail(FoundryAuthorityModel):
    status: Literal["fail"]
    profile_id: IdentityText
    failures: Annotated[
        tuple[AuthorityPredicateFailure, ...],
        Field(min_length=1),
    ]


DependencyProfileReconciliation = Annotated[
    DependencyProfileReconciliationPass | DependencyProfileReconciliationFail,
    Field(discriminator="status"),
]


def declaration_ref(
    declaration: MethodCatalogDependencyProfileDeclaration,
) -> FoundryRecordRef[Literal[DigestDomain.PROFILE_DECLARATION]]:
    """Recompute a declaration reference from its strict semantic statement."""

    raw = canonical_json_bytes(declaration.model_dump(mode="json"))
    return record_ref(
        DigestDomain.PROFILE_DECLARATION,
        raw,
        schema_version=declaration.schema_version,
    )


def load_dependency_profile_registry(path: Path) -> DependencyProfileRegistryStatement:
    """Decode the strict tracked profile registry without implicit defaults."""

    wire = tomllib.loads(path.read_text(encoding="utf-8"))
    if set(wire) != {"schema_version", "declarations"}:
        raise ValueError("profile registry has unknown or missing top-level fields")
    declarations: list[MethodCatalogDependencyProfileDeclaration] = []
    expected_fields = {
        "schema_version",
        "profile_id",
        "root_distribution",
        "extras",
        "python_constraint",
        "resolver_name",
        "resolver_version",
        "pyproject_sha256",
        "uv_lock_sha256",
    }
    for row in wire["declarations"]:
        if set(row) != expected_fields:
            raise ValueError("profile declaration has unknown or missing fields")
        extras = row["extras"]
        if type(extras) is not list or any(type(item) is not str for item in extras):
            raise ValueError("profile extras must be exact strings")
        declarations.append(
            MethodCatalogDependencyProfileDeclaration(
                schema_version=row["schema_version"],
                profile_id=row["profile_id"],
                root_distribution=row["root_distribution"],
                extras=tuple(extras),
                python_constraint=row["python_constraint"],
                resolver_name=row["resolver_name"],
                resolver_version=row["resolver_version"],
                pyproject_ref=DomainDigest[Literal[DigestDomain.PYPROJECT]](
                    domain=DigestDomain.PYPROJECT,
                    value=row["pyproject_sha256"],
                ),
                lockfile_ref=DomainDigest[Literal[DigestDomain.UV_LOCK]](
                    domain=DigestDomain.UV_LOCK,
                    value=row["uv_lock_sha256"],
                ),
            )
        )
    return DependencyProfileRegistryStatement(
        schema_version=wire["schema_version"],
        declarations=tuple(declarations),
    )


def resolve_profile_declaration(
    registry: DependencyProfileRegistryStatement,
    *,
    profile_id: str,
) -> MethodCatalogDependencyProfileDeclaration:
    """Resolve exactly one data row; a novel row requires no code branch."""

    matches = tuple(row for row in registry.declarations if row.profile_id == profile_id)
    if len(matches) != 1:
        raise ValueError("dependency profile must resolve to exactly one declaration")
    return matches[0]


def _collect_marker_variables(node: object, destination: set[str]) -> None:
    if isinstance(node, (list, tuple)):
        for child in node:
            _collect_marker_variables(child, destination)
        return
    if type(node).__name__ == "Variable":
        value = getattr(node, "value", None)
        if type(value) is str:
            destination.add(value)


def _marker_selected(
    edge: Mapping[str, object],
    marker_environment: Mapping[str, str],
    *,
    used_marker_keys: set[str],
) -> bool:
    marker = edge.get("marker")
    if marker is None:
        return True
    if type(marker) is not str:
        raise ValueError("lock marker must be an exact string")
    parsed = Marker(marker)
    _collect_marker_variables(parsed._markers, used_marker_keys)
    return parsed.evaluate(environment=dict(marker_environment))


def _selected_lock_rows(
    *,
    lock: Mapping[str, object],
    declaration: MethodCatalogDependencyProfileDeclaration,
    marker_environment: Mapping[str, str],
    used_marker_keys: set[str],
) -> tuple[Mapping[str, object], ...]:
    packages_raw = lock.get("package")
    if type(packages_raw) is not list:
        raise ValueError("uv lock package denominator is missing")
    packages = tuple(row for row in packages_raw if isinstance(row, Mapping))
    by_name: dict[str, Mapping[str, object]] = {}
    for row in packages:
        name = row.get("name")
        if type(name) is not str:
            raise ValueError("uv lock package name is invalid")
        canonical_name = canonicalize_name(name)
        if canonical_name in by_name:
            raise ValueError("uv lock contains an ambiguous package name")
        by_name[canonical_name] = row
    root_name = canonicalize_name(declaration.root_distribution)
    root = by_name.get(root_name)
    if root is None:
        raise ValueError("root distribution is absent from uv lock")
    pending: deque[str] = deque([root_name])
    optional = root.get("optional-dependencies")
    if not isinstance(optional, Mapping):
        raise ValueError("root optional-dependency table is missing")
    for extra in declaration.extras:
        edges = optional.get(extra)
        if type(edges) is not list:
            raise ValueError(f"admitted extra is absent from uv lock: {extra}")
        for edge in edges:
            if not isinstance(edge, Mapping) or type(edge.get("name")) is not str:
                raise ValueError("optional dependency edge is invalid")
            if _marker_selected(
                edge,
                marker_environment,
                used_marker_keys=used_marker_keys,
            ):
                pending.append(canonicalize_name(edge["name"]))
    selected: dict[str, Mapping[str, object]] = {}
    while pending:
        name = pending.popleft()
        if name in selected:
            continue
        row = by_name.get(name)
        if row is None:
            raise ValueError(f"selected dependency is absent from uv lock: {name}")
        selected[name] = row
        edges = row.get("dependencies", [])
        if type(edges) is not list:
            raise ValueError("dependency edge set is invalid")
        for edge in edges:
            if not isinstance(edge, Mapping) or type(edge.get("name")) is not str:
                raise ValueError("dependency edge is invalid")
            if _marker_selected(
                edge,
                marker_environment,
                used_marker_keys=used_marker_keys,
            ):
                pending.append(canonicalize_name(edge["name"]))
    return tuple(selected[name] for name in sorted(selected))


def resolve_dependency_profile(
    declaration: MethodCatalogDependencyProfileDeclaration,
    *,
    pyproject_bytes: bytes,
    lockfile_bytes: bytes,
    marker_environment: Mapping[str, str],
    production_data_manifest: ProductionDataManifestInput,
    admission: MethodCatalogProfileAdmission,
) -> ResolvedMethodCatalogDependencyProfile | DependencyProfileCandidateFailure:
    """Derive a candidate closure or one exact typed input failure."""

    if isinstance(production_data_manifest, ProductionDataManifestUnavailable):
        return ProductionDataManifestMissingFailure(
            kind="production_data_manifest_missing",
            predicate_id=AuthorityPredicateId.PRODUCTION_MANIFEST,
            code=AuthorityFailureCode.MANIFEST_MISSING,
            cause=production_data_manifest.cause,
            predicate_class="not_established",
        )
    actual_declaration_ref = declaration_ref(declaration)
    if admission.profile_id != declaration.profile_id:
        return ScalarPredicateMismatch(
            kind="scalar_mismatch",
            predicate_id=AuthorityPredicateId.PURPOSE_PROFILE,
            code=AuthorityFailureCode.PROFILE_MISMATCH,
            expected=DomainScalar(
                domain=ScalarDomain.PROFILE_ID,
                value=declaration.profile_id,
            ),
            observed=DomainScalar(
                domain=ScalarDomain.PROFILE_ID,
                value=admission.profile_id,
            ),
            predicate_class="recomputed",
        )
    if admission.declaration_ref != actual_declaration_ref:
        return DigestPredicateMismatch(
            kind="digest_mismatch",
            predicate_id=AuthorityPredicateId.PURPOSE_PROFILE,
            code=AuthorityFailureCode.PROFILE_MISMATCH,
            expected=actual_declaration_ref.semantic_hash,
            observed=admission.declaration_ref.semantic_hash,
            predicate_class="recomputed",
        )
    for _field, domain, raw, expected in (
        ("pyproject_ref", DigestDomain.PYPROJECT, pyproject_bytes, declaration.pyproject_ref),
        ("lockfile_ref", DigestDomain.UV_LOCK, lockfile_bytes, declaration.lockfile_ref),
    ):
        observed = domain_digest(domain, raw)
        if observed != expected:
            return DigestPredicateMismatch(
                kind="digest_mismatch",
                predicate_id=AuthorityPredicateId.PURPOSE_PROFILE,
                code=AuthorityFailureCode.PROFILE_MISMATCH,
                expected=expected,
                observed=observed,
                predicate_class="recomputed",
            )
    try:
        pyproject = tomllib.loads(pyproject_bytes.decode("utf-8"))
        project = pyproject["project"]
        lock = tomllib.loads(lockfile_bytes.decode("utf-8"))
        if canonicalize_name(project["name"]) != canonicalize_name(
            declaration.root_distribution
        ):
            raise ValueError("root distribution mismatch")
        used_marker_keys: set[str] = set()
        rows = _selected_lock_rows(
            lock=lock,
            declaration=declaration,
            marker_environment=marker_environment,
            used_marker_keys=used_marker_keys,
        )
    except (KeyError, TypeError, UnicodeDecodeError, tomllib.TOMLDecodeError, ValueError) as exc:
        return DependencyProfileInputMismatch(
            kind="dependency_profile_input_mismatch",
            predicate_id=AuthorityPredicateId.PURPOSE_PROFILE,
            code=AuthorityFailureCode.PROFILE_MISMATCH,
            field="selected_lock_graph",
            expected=declaration.root_distribution,
            observed=type(exc).__name__,
            predicate_class="recomputed",
        )
    distributions: list[LockedDistributionIdentity] = []
    for row in rows:
        canonical_row = canonical_json_bytes(dict(row))
        distributions.append(
            LockedDistributionIdentity(
                name=canonicalize_name(str(row["name"])),
                version=str(row.get("version") or "editable"),
                source_kind=next(iter(row.get("source", {"unknown": ""}))),
                selected_artifact=domain_digest(
                    DigestDomain.SELECTED_DISTRIBUTION, canonical_row
                ),
            )
        )
    marker_rows = tuple(
        sorted(
            (key, str(marker_environment[key]))
            for key in used_marker_keys
            if key in marker_environment
        )
    )
    distribution_rows = [row.model_dump(mode="json") for row in distributions]
    distribution_set = domain_digest(
        DigestDomain.DISTRIBUTION_SET, canonical_json_bytes(distribution_rows)
    )
    stable_content_set = domain_digest(
        DigestDomain.CONTENT_SET_STABLE,
        canonical_json_bytes([row["selected_artifact"] for row in distribution_rows]),
    )
    manifest_ref = record_ref(
        DigestDomain.PRODUCTION_MANIFEST,
        production_data_manifest.exact_bytes,
        schema_version="polisyos.foundry.production-data-manifest.v1",
    )
    closure_statement = {
        "declaration_ref": actual_declaration_ref.model_dump(mode="json"),
        "marker_environment": marker_rows,
        "distribution_set": distribution_set.model_dump(mode="json"),
        "stable_content_set": stable_content_set.model_dump(mode="json"),
        "production_data_manifest_ref": manifest_ref.model_dump(mode="json"),
    }
    return ResolvedMethodCatalogDependencyProfile(
        status="resolved",
        admission=admission,
        declaration=declaration,
        marker_environment=marker_rows,
        distributions=tuple(distributions),
        distribution_set=distribution_set,
        stable_content_set=stable_content_set,
        stable_closure=domain_digest(
            DigestDomain.DEPENDENCY_CLOSURE,
            canonical_json_bytes(closure_statement),
        ),
        production_data_manifest_ref=manifest_ref,
    )


class DependencyProfileEnvironmentEvidence(Protocol):
    """Read exact candidate evidence by its content-bound Foundry ref."""

    def read_blob(self, *, record_ref: FoundryRecordRef[DigestDomain]) -> bytes: ...


_ENVIRONMENT_MARKER_RELATIVE_PATH = Path(
    ".polisyos-foundry-authority-v1/environment-marker.json"
)


def _profile_admission_ref(
    admission: MethodCatalogProfileAdmission,
) -> FoundryRecordRef[Literal[DigestDomain.PROFILE_ADMISSION]]:
    return record_ref(
        DigestDomain.PROFILE_ADMISSION,
        canonical_json_bytes(admission.model_dump(mode="json")),
        schema_version=admission.schema_version,
    )


def _missing_environment_marker() -> MissingPredicateEvidence:
    return MissingPredicateEvidence(
        kind="not_established",
        predicate_id=AuthorityPredicateId.ENVIRONMENT_RECEIPT,
        code=AuthorityFailureCode.ENVIRONMENT_NOT_ESTABLISHED,
        missing_domains=(DigestDomain.ENVIRONMENT_RECEIPT,),
        predicate_class="not_established",
    )


def _reopen_bound_environment_marker(
    *,
    environment_root: Path,
    expected_marker_ref: FoundryRecordRef[
        Literal[DigestDomain.ENVIRONMENT_MARKER]
    ],
    evidence: DependencyProfileEnvironmentEvidence,
) -> DependencyEnvironmentMarkerStatement | AuthorityPredicateFailure:
    """Reopen one target marker from both its bound path and retained bytes."""

    marker_path = environment_root / _ENVIRONMENT_MARKER_RELATIVE_PATH
    try:
        marker_raw = marker_path.read_bytes()
        retained_marker_raw = evidence.read_blob(record_ref=expected_marker_ref)
    except (FileNotFoundError, OSError, ValueError):
        return _missing_environment_marker()

    observed_marker_ref = record_ref(
        DigestDomain.ENVIRONMENT_MARKER,
        marker_raw,
        schema_version=expected_marker_ref.schema_version,
    )
    if marker_raw != retained_marker_raw or observed_marker_ref != expected_marker_ref:
        return DigestPredicateMismatch(
            kind="digest_mismatch",
            predicate_id=AuthorityPredicateId.ENVIRONMENT_RECEIPT,
            code=AuthorityFailureCode.ENVIRONMENT_MISMATCH,
            expected=expected_marker_ref.semantic_hash,
            observed=observed_marker_ref.semantic_hash,
            predicate_class="independently_reconciled",
        )
    try:
        return DependencyEnvironmentMarkerStatement.model_validate_json(marker_raw)
    except ValueError:
        return _missing_environment_marker()


def reconcile_bound_installed_environment(
    profile: ResolvedMethodCatalogDependencyProfile,
    *,
    environment_root: Path,
    environment_receipt: DependencyProfileEnvironmentReceipt,
    evidence: DependencyProfileEnvironmentEvidence,
) -> DependencyProfileReconciliation:
    """Reopen the target marker and reconcile only the selected closure."""

    statement = environment_receipt.statement
    expected_names = {row.name for row in profile.distributions}
    expected = {
        (row.name, row.version, row.selected_artifact.value)
        for row in profile.distributions
    }
    observed = {
        (
            row.normalized_name,
            row.version,
            row.selected_artifact_ref.semantic_hash.value,
        )
        for row in statement.observed_distributions
        if row.normalized_name in expected_names
    }
    failures: list[AuthorityPredicateFailure] = []
    expected_admission_ref = _profile_admission_ref(profile.admission)
    if statement.admission_ref != expected_admission_ref:
        failures.append(
            DigestPredicateMismatch(
                kind="digest_mismatch",
                predicate_id=AuthorityPredicateId.PURPOSE_PROFILE,
                code=AuthorityFailureCode.PROFILE_MISMATCH,
                expected=expected_admission_ref.semantic_hash,
                observed=statement.admission_ref.semantic_hash,
                predicate_class="independently_reconciled",
            )
        )

    reopened_marker = _reopen_bound_environment_marker(
        environment_root=environment_root,
        expected_marker_ref=statement.marker_ref,
        evidence=evidence,
    )
    if not isinstance(reopened_marker, DependencyEnvironmentMarkerStatement):
        failures.append(reopened_marker)
        return DependencyProfileReconciliationFail(
            status="fail",
            profile_id=profile.declaration.profile_id,
            failures=tuple(failures),
        )
    marker = reopened_marker
    observed_statement = statement.model_copy(
        update={
            "stable_closure": marker.stable_closure,
            "python_runtime_installation_ref": marker.python_runtime_installation_ref,
            "python_runtime_verification_ref": marker.python_runtime_verification_ref,
            "instance_content_set": marker.instance_content_set,
        }
    )
    if observed_statement != statement:
        observed_receipt_ref = record_ref(
            DigestDomain.ENVIRONMENT_RECEIPT,
            canonical_json_bytes(observed_statement.model_dump(mode="json")),
            schema_version=observed_statement.schema_version,
        )
        failures.append(
            DigestPredicateMismatch(
                kind="digest_mismatch",
                predicate_id=AuthorityPredicateId.ENVIRONMENT_RECEIPT,
                code=AuthorityFailureCode.ENVIRONMENT_MISMATCH,
                expected=environment_receipt.receipt_ref.semantic_hash,
                observed=observed_receipt_ref.semantic_hash,
                predicate_class="independently_reconciled",
            )
        )

    if observed != expected or statement.stable_content_set != profile.stable_content_set:
        observed_by_name = {
            row.normalized_name: row
            for row in statement.observed_distributions
            if row.normalized_name in expected_names
        }
        observed_content_set = domain_digest(
            DigestDomain.CONTENT_SET_STABLE,
            canonical_json_bytes(
                [
                    observed_by_name[row.name]
                    .selected_artifact_ref.semantic_hash.model_dump(mode="json")
                    for row in profile.distributions
                    if row.name in observed_by_name
                ]
            ),
        )
        failures.append(
            DigestPredicateMismatch(
                kind="digest_mismatch",
                predicate_id=AuthorityPredicateId.INSTALLED_CONTENT,
                code=AuthorityFailureCode.CONTENT_MISMATCH,
                expected=profile.stable_content_set,
                observed=observed_content_set,
                predicate_class="independently_reconciled",
            )
        )
    elif statement.stable_closure != profile.stable_closure:
        failures.append(
            DigestPredicateMismatch(
                kind="digest_mismatch",
                predicate_id=AuthorityPredicateId.ENVIRONMENT_RECEIPT,
                code=AuthorityFailureCode.ENVIRONMENT_MISMATCH,
                expected=profile.stable_closure,
                observed=statement.stable_closure,
                predicate_class="independently_reconciled",
            )
        )
    if failures:
        return DependencyProfileReconciliationFail(
            status="fail",
            profile_id=profile.declaration.profile_id,
            failures=tuple(failures),
        )
    return DependencyProfileReconciliationPass(
        status="pass",
        profile_id=profile.declaration.profile_id,
        stable_closure=profile.stable_closure,
        environment_receipt_ref=environment_receipt.receipt_ref,
        predicate_class="independently_reconciled",
    )


__all__ = [
    "DependencyProfileCandidateFailure",
    "DependencyProfileEnvironmentReceipt",
    "DependencyProfileInputMismatch",
    "DependencyProfileRegistryStatement",
    "LockedDistributionIdentity",
    "MethodCatalogDependencyProfileDeclaration",
    "MethodCatalogProfileAdmission",
    "ObservedInstalledDistribution",
    "ProductionDataManifestInput",
    "ProductionDataManifestMissingFailure",
    "ProductionDataManifestPresent",
    "ProductionDataManifestUnavailable",
    "ResolvedMethodCatalogDependencyProfile",
    "declaration_ref",
    "load_dependency_profile_registry",
    "reconcile_bound_installed_environment",
    "resolve_dependency_profile",
    "resolve_profile_declaration",
    "read_candidate_production_data_manifest",
]
