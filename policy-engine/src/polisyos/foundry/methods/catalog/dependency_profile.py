"""Pure candidate reducers for Foundry dependency-profile identity.

These reducers construct content-bound candidate evidence only.  The production
authority path in :mod:`dependency_authority` currently refuses before it can
admit or persist any value produced here.
"""

from __future__ import annotations

import tomllib
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Annotated, Literal, Protocol

from packaging.markers import Marker
from packaging.utils import canonicalize_name
from pydantic import Field, TypeAdapter, ValidationError, model_validator

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


class DependencyProfileDiscriminant(FoundryAuthorityModel):
    """Dependency-only profile identity recomputed from tracked owner bytes."""

    schema_version: Literal["polisyos.foundry.dependency-discriminant.v1"]
    rule_version: Literal["polisyos.foundry.dependency_discriminant.v1"]
    profile_id: IdentityText
    declaration_ref: FoundryRecordRef[Literal[DigestDomain.PROFILE_DECLARATION]]
    root_distribution: IdentityText
    extras: tuple[IdentityText, ...]
    python_constraint: IdentityText
    resolver_name: Literal["uv"]
    resolver_version: Literal["0.9.21"]
    pyproject_ref: DomainDigest[Literal[DigestDomain.PYPROJECT]]
    lockfile_ref: DomainDigest[Literal[DigestDomain.UV_LOCK]]
    marker_environment: tuple[tuple[EnvironmentKeyText, EnvironmentValueText], ...]
    resolved_distributions: tuple[LockedDistributionIdentity, ...]
    distribution_set: DomainDigest[Literal[DigestDomain.DISTRIBUTION_SET]]
    discriminant_ref: DomainDigest[Literal[DigestDomain.DEPENDENCY_DISCRIMINANT]]

    @property
    def distributions(self) -> tuple[LockedDistributionIdentity, ...]:
        """Expose the resolved closure under the established reducer attribute."""

        return self.resolved_distributions

    @model_validator(mode="after")
    def validate_content_binding(self) -> DependencyProfileDiscriminant:
        names = tuple(row.name for row in self.resolved_distributions)
        if not names or names != tuple(sorted(set(names))):
            raise ValueError("resolved distributions must be non-empty, sorted and unique")
        if self.extras != tuple(sorted(set(self.extras))):
            raise ValueError("discriminant extras must be sorted and unique")
        if self.marker_environment != tuple(sorted(set(self.marker_environment))):
            raise ValueError("marker environment must be sorted and unique")
        rows = [row.model_dump(mode="json") for row in self.resolved_distributions]
        expected_distribution_set = domain_digest(
            DigestDomain.DISTRIBUTION_SET,
            canonical_json_bytes(rows),
        )
        if self.distribution_set != expected_distribution_set:
            raise ValueError("distribution set is not bound to the resolved rows")
        expected_discriminant = domain_digest(
            DigestDomain.DEPENDENCY_DISCRIMINANT,
            canonical_json_bytes(
                self.model_dump(mode="json", exclude={"discriminant_ref"})
            ),
        )
        if self.discriminant_ref != expected_discriminant:
            raise ValueError("discriminant ref is not bound to the dependency statement")
        return self


class InstalledDistributionObservation(FoundryAuthorityModel):
    """Ambient installed coordinates without source or artifact authority."""

    name: IdentityText
    version: IdentityText


class RootDistributionDiagnosticCase(FoundryAuthorityModel):
    """The observed closure does not contain the declared root distribution."""

    case_kind: Literal["root_distribution_disagreement"]
    coordinate: IdentityText
    expected: IdentityText
    observed: IdentityText
    predicate_class: Literal["independently_reconciled", "recomputed"]


class MissingDistributionDiagnosticCase(FoundryAuthorityModel):
    """One resolved distribution is absent from the installed observation."""

    case_kind: Literal["missing_resolved_distribution"]
    coordinate: IdentityText
    expected: IdentityText
    observed: IdentityText
    predicate_class: Literal["independently_reconciled", "recomputed"]


class DistributionFieldDiagnosticCase(FoundryAuthorityModel):
    """One independently observable distribution coordinate disagrees."""

    case_kind: Literal["distribution_field_disagreement"]
    coordinate: IdentityText
    field: Literal["version", "source_kind", "selected_artifact"]
    expected: IdentityText
    observed: IdentityText
    predicate_class: Literal["independently_reconciled", "recomputed"]


class UnexpectedInClosureIdentityDiagnosticCase(FoundryAuthorityModel):
    """An installed observation ambiguously repeats an in-closure identity."""

    case_kind: Literal["unexpected_in_closure_identity"]
    coordinate: IdentityText
    expected: IdentityText
    observed: IdentityText
    predicate_class: Literal["independently_reconciled", "recomputed"]


DependencyEnvironmentDiagnosticCase = Annotated[
    RootDistributionDiagnosticCase
    | MissingDistributionDiagnosticCase
    | DistributionFieldDiagnosticCase
    | UnexpectedInClosureIdentityDiagnosticCase,
    Field(discriminator="case_kind"),
]


class DependencyEnvironmentDiagnosticPass(FoundryAuthorityModel):
    """The observable installed coordinates match the dependency closure."""

    status: Literal["pass"]
    ordered_cases: tuple[DependencyEnvironmentDiagnosticCase, ...]
    first_case: None
    predicate_class: Literal["recomputed"]

    @model_validator(mode="after")
    def validate_empty_cases(self) -> DependencyEnvironmentDiagnosticPass:
        if self.ordered_cases:
            raise ValueError("passing diagnostics cannot carry cases")
        return self


class DependencyEnvironmentDiagnosticFail(FoundryAuthorityModel):
    """One or more observable coordinates disagree with the dependency closure."""

    status: Literal["fail"]
    ordered_cases: Annotated[
        tuple[DependencyEnvironmentDiagnosticCase, ...],
        Field(min_length=1),
    ]
    first_case: DependencyEnvironmentDiagnosticCase
    predicate_class: Literal["independently_reconciled", "recomputed"]

    @model_validator(mode="after")
    def validate_first_case(self) -> DependencyEnvironmentDiagnosticFail:
        if self.first_case != self.ordered_cases[0]:
            raise ValueError("first case must be the first ordered case")
        return self


class DependencyEnvironmentDiagnosticNotEstablished(FoundryAuthorityModel):
    """Required independently observable source evidence was not received."""

    status: Literal["not_established"]
    code: Literal["installed_distribution_source_evidence_not_established"]
    missing_coordinates: Annotated[tuple[IdentityText, ...], Field(min_length=1)]
    predicate_class: Literal["not_established"]


DependencyEnvironmentDiagnosticResult = Annotated[
    DependencyEnvironmentDiagnosticPass
    | DependencyEnvironmentDiagnosticFail
    | DependencyEnvironmentDiagnosticNotEstablished,
    Field(discriminator="status"),
]


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


def _environment_receipt_ref(
    statement: DependencyProfileEnvironmentStatement,
) -> FoundryRecordRef[Literal[DigestDomain.ENVIRONMENT_RECEIPT]]:
    return record_ref(
        DigestDomain.ENVIRONMENT_RECEIPT,
        canonical_json_bytes(statement.model_dump(mode="json")),
        schema_version=statement.schema_version,
    )


class DependencyProfileEnvironmentReceipt(FoundryAuthorityModel):
    """Candidate instance evidence; it is not writer-independent custody."""

    receipt_ref: FoundryRecordRef[Literal[DigestDomain.ENVIRONMENT_RECEIPT]]
    statement: DependencyProfileEnvironmentStatement
    predicate_class: Literal["recomputed"]

    @model_validator(mode="after")
    def validate_content_binding(self) -> DependencyProfileEnvironmentReceipt:
        expected = _environment_receipt_ref(self.statement)
        if self.receipt_ref != expected:
            raise ValueError("environment receipt is not content-bound")
        return self


class AmbientDependencyEnvironmentObservation(FoundryAuthorityModel):
    """Ambient name/version observations with no source-identity claim."""

    observation_kind: Literal["ambient"]
    distributions: tuple[InstalledDistributionObservation, ...]


class ReceiptBackedDependencyEnvironmentObservation(FoundryAuthorityModel):
    """Candidate distribution evidence carried by a Foundry environment receipt."""

    observation_kind: Literal["foundry_environment_receipt"]
    environment_receipt: DependencyProfileEnvironmentReceipt


DependencyEnvironmentObservation = Annotated[
    AmbientDependencyEnvironmentObservation
    | ReceiptBackedDependencyEnvironmentObservation,
    Field(discriminator="observation_kind"),
]


_DEPENDENCY_ENVIRONMENT_OBSERVATION_ADAPTER = TypeAdapter(
    DependencyEnvironmentObservation
)


@dataclass(frozen=True, slots=True)
class _ComparableInstalledDistribution:
    """Internal coordinates after the observation variant has been resolved."""

    name: str
    version: str
    source_kind: str | None
    selected_artifact: (
        DomainDigest[Literal[DigestDomain.SELECTED_DISTRIBUTION]] | None
    )


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


def decode_dependency_profile_registry_toml(
    raw_toml_bytes: bytes,
) -> DependencyProfileRegistryStatement:
    """Decode exact dependency-profile registry bytes without implicit defaults.

    Args:
        raw_toml_bytes: Exact TOML bytes from a tracked or frozen owner source.

    Returns:
        The strict, immutable profile registry statement.

    Raises:
        ValueError: If the bytes are not UTF-8 TOML with the exact registry shape.
    """

    try:
        wire = tomllib.loads(raw_toml_bytes.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("dependency profile registry bytes are invalid") from exc
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


def load_dependency_profile_registry(path: Path) -> DependencyProfileRegistryStatement:
    """Read and decode the strict tracked profile registry."""

    return decode_dependency_profile_registry_toml(path.read_bytes())


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


def resolve_profile_declaration_for_purpose(
    registry: DependencyProfileRegistryStatement,
    *,
    authority_registry_bytes: bytes,
    authority_purpose: Literal["n8_method_catalog_reconstruction"],
) -> MethodCatalogDependencyProfileDeclaration:
    """Resolve and content-bind the one owner profile admitted for a purpose.

    Args:
        registry: Strict tracked dependency-profile registry.
        authority_registry_bytes: Exact tracked Foundry authority registry.
        authority_purpose: Owner purpose; callers cannot provide a profile ID.

    Returns:
        The uniquely admitted declaration after both reference fields verify.

    Raises:
        ValueError: If the purpose row is missing, ambiguous, or not bound to
            the selected declaration.
    """

    wire = tomllib.loads(authority_registry_bytes.decode("utf-8"))
    admissions = wire.get("purpose_admissions")
    if type(admissions) is not list:
        raise ValueError("authority purpose admission denominator is missing")
    matches = tuple(
        row
        for row in admissions
        if isinstance(row, Mapping)
        and row.get("authority_purpose") == authority_purpose
    )
    if len(matches) != 1:
        raise ValueError("authority purpose must resolve to exactly one profile")
    row = matches[0]
    if set(row) != {
        "authority_purpose",
        "profile_id",
        "declaration_artifact_id",
        "declaration_semantic_hash",
        "predicate_class",
    } or row.get("predicate_class") != "recomputed":
        raise ValueError("authority purpose admission has an invalid shape")
    profile_id = row.get("profile_id")
    if type(profile_id) is not str:
        raise ValueError("authority purpose profile identity is invalid")
    declaration = resolve_profile_declaration(registry, profile_id=profile_id)
    reference = declaration_ref(declaration)
    if (
        row.get("declaration_artifact_id") != reference.artifact_id
        or row.get("declaration_semantic_hash") != reference.semantic_hash.value
    ):
        raise ValueError("authority purpose admission is not content-bound")
    return declaration


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
    marker_keys: set[str] = set()
    _collect_marker_variables(parsed._markers, marker_keys)
    used_marker_keys.update(marker_keys)
    missing_marker_keys = marker_keys.difference(marker_environment)
    if missing_marker_keys:
        raise ValueError(
            "marker environment is missing used keys: "
            + ",".join(sorted(missing_marker_keys))
        )
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


def _validate_profile_admission(
    declaration: MethodCatalogDependencyProfileDeclaration,
    admission: MethodCatalogProfileAdmission,
) -> DigestPredicateMismatch | ScalarPredicateMismatch | None:
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
    return None


def resolve_dependency_discriminant(
    declaration: MethodCatalogDependencyProfileDeclaration,
    *,
    pyproject_bytes: bytes,
    lockfile_bytes: bytes,
    marker_environment: Mapping[str, str],
) -> DependencyProfileDiscriminant | DependencyProfileInputMismatch | DigestPredicateMismatch:
    """Resolve a dependency-only discriminant from tracked owner inputs.

    Args:
        declaration: Strict owner declaration for the selected root and extras.
        pyproject_bytes: Exact tracked ``pyproject.toml`` bytes.
        lockfile_bytes: Exact tracked ``uv.lock`` bytes.
        marker_environment: PEP 508 environment used for the selected graph walk.

    Returns:
        The content-bound dependency discriminant, or one typed recomputation
        failure. The reducer never reads production data or installed state.
    """

    actual_declaration_ref = declaration_ref(declaration)
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
        )
    )
    distribution_rows = [row.model_dump(mode="json") for row in distributions]
    distribution_set = domain_digest(
        DigestDomain.DISTRIBUTION_SET, canonical_json_bytes(distribution_rows)
    )
    statement = {
        "schema_version": "polisyos.foundry.dependency-discriminant.v1",
        "rule_version": "polisyos.foundry.dependency_discriminant.v1",
        "profile_id": declaration.profile_id,
        "declaration_ref": actual_declaration_ref.model_dump(mode="json"),
        "root_distribution": canonicalize_name(declaration.root_distribution),
        "extras": declaration.extras,
        "python_constraint": declaration.python_constraint,
        "resolver_name": declaration.resolver_name,
        "resolver_version": declaration.resolver_version,
        "pyproject_ref": declaration.pyproject_ref.model_dump(mode="json"),
        "lockfile_ref": declaration.lockfile_ref.model_dump(mode="json"),
        "marker_environment": marker_rows,
        "resolved_distributions": distribution_rows,
        "distribution_set": distribution_set.model_dump(mode="json"),
    }
    return DependencyProfileDiscriminant(
        schema_version="polisyos.foundry.dependency-discriminant.v1",
        rule_version="polisyos.foundry.dependency_discriminant.v1",
        profile_id=declaration.profile_id,
        declaration_ref=actual_declaration_ref,
        root_distribution=canonicalize_name(declaration.root_distribution),
        extras=declaration.extras,
        python_constraint=declaration.python_constraint,
        resolver_name=declaration.resolver_name,
        resolver_version=declaration.resolver_version,
        pyproject_ref=declaration.pyproject_ref,
        lockfile_ref=declaration.lockfile_ref,
        marker_environment=marker_rows,
        resolved_distributions=tuple(distributions),
        distribution_set=distribution_set,
        discriminant_ref=domain_digest(
            DigestDomain.DEPENDENCY_DISCRIMINANT,
            canonical_json_bytes(statement),
        ),
    )


def resolve_dependency_profile(
    declaration: MethodCatalogDependencyProfileDeclaration,
    *,
    pyproject_bytes: bytes,
    lockfile_bytes: bytes,
    marker_environment: Mapping[str, str],
    production_data_manifest: ProductionDataManifestInput,
    admission: MethodCatalogProfileAdmission,
) -> ResolvedMethodCatalogDependencyProfile | DependencyProfileCandidateFailure:
    """Derive the existing production-manifest-composed candidate closure."""

    if isinstance(production_data_manifest, ProductionDataManifestUnavailable):
        return ProductionDataManifestMissingFailure(
            kind="production_data_manifest_missing",
            predicate_id=AuthorityPredicateId.PRODUCTION_MANIFEST,
            code=AuthorityFailureCode.MANIFEST_MISSING,
            cause=production_data_manifest.cause,
            predicate_class="not_established",
        )
    admission_failure = _validate_profile_admission(declaration, admission)
    if admission_failure is not None:
        return admission_failure
    discriminant = resolve_dependency_discriminant(
        declaration,
        pyproject_bytes=pyproject_bytes,
        lockfile_bytes=lockfile_bytes,
        marker_environment=marker_environment,
    )
    if not isinstance(discriminant, DependencyProfileDiscriminant):
        return discriminant
    distribution_rows = [
        row.model_dump(mode="json") for row in discriminant.resolved_distributions
    ]
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
        "declaration_ref": discriminant.declaration_ref.model_dump(mode="json"),
        "marker_environment": discriminant.marker_environment,
        "distribution_set": discriminant.distribution_set.model_dump(mode="json"),
        "stable_content_set": stable_content_set.model_dump(mode="json"),
        "production_data_manifest_ref": manifest_ref.model_dump(mode="json"),
    }
    return ResolvedMethodCatalogDependencyProfile(
        status="resolved",
        admission=admission,
        declaration=declaration,
        marker_environment=discriminant.marker_environment,
        distributions=discriminant.resolved_distributions,
        distribution_set=discriminant.distribution_set,
        stable_content_set=stable_content_set,
        stable_closure=domain_digest(
            DigestDomain.DEPENDENCY_CLOSURE,
            canonical_json_bytes(closure_statement),
        ),
        production_data_manifest_ref=manifest_ref,
    )


def observe_installed_distributions(
    discriminant: DependencyProfileDiscriminant,
    *,
    installed_distributions: Iterable[metadata.Distribution] | None = None,
) -> AmbientDependencyEnvironmentObservation:
    """Observe generic installed name/version coordinates for the resolved closure.

    Args:
        discriminant: Recomputed dependency closure that defines the complete
            comparison population.
        installed_distributions: Optional metadata population used by tests or
            another observer. Defaults to the current interpreter metadata.

    Returns:
        One explicit ambient observation containing sorted rows projected only
        onto names in the resolved closure. Source and selected-artifact
        identity are absent because Python metadata is not a Foundry receipt.
    """

    expected_names = {row.name for row in discriminant.resolved_distributions}
    observed: list[InstalledDistributionObservation] = []
    population = (
        metadata.distributions()
        if installed_distributions is None
        else installed_distributions
    )
    for distribution in population:
        raw_name = distribution.metadata.get("Name")
        raw_version = distribution.version
        if not raw_name or not raw_version:
            continue
        name = canonicalize_name(raw_name)
        if name not in expected_names:
            continue
        observed.append(
            InstalledDistributionObservation(
                name=name,
                version=raw_version,
            )
        )
    return AmbientDependencyEnvironmentObservation(
        observation_kind="ambient",
        distributions=tuple(sorted(observed, key=lambda row: (row.name, row.version))),
    )


def _source_evidence_not_established(
    discriminant: DependencyProfileDiscriminant,
) -> DependencyEnvironmentDiagnosticNotEstablished:
    return DependencyEnvironmentDiagnosticNotEstablished(
        status="not_established",
        code="installed_distribution_source_evidence_not_established",
        missing_coordinates=tuple(
            f"distribution:{row.name}:source_kind"
            for row in discriminant.resolved_distributions
        ),
        predicate_class="not_established",
    )


def _resolve_receipt_backed_distributions(
    *,
    discriminant: DependencyProfileDiscriminant,
    observation: ReceiptBackedDependencyEnvironmentObservation,
    environment_root: Path | None,
    evidence: DependencyProfileEnvironmentEvidence | None,
) -> (
    tuple[_ComparableInstalledDistribution, ...]
    | DependencyEnvironmentDiagnosticNotEstablished
):
    if environment_root is None or evidence is None:
        return _source_evidence_not_established(discriminant)
    statement = _reopen_reconciled_environment_statement(
        environment_root=environment_root,
        environment_receipt=observation.environment_receipt,
        evidence=evidence,
    )
    if not isinstance(statement, DependencyProfileEnvironmentStatement):
        return _source_evidence_not_established(discriminant)
    return tuple(
        _ComparableInstalledDistribution(
            name=canonicalize_name(row.normalized_name),
            version=row.version,
            source_kind=row.source_kind,
            selected_artifact=row.selected_artifact_ref.semantic_hash,
        )
        for row in statement.observed_distributions
    )


def _normalize_distribution_observations(
    *,
    discriminant: DependencyProfileDiscriminant,
    observed_distributions: (
        DependencyEnvironmentObservation
        | Mapping[str, object]
        | Sequence[Mapping[str, object]]
    ),
    environment_root: Path | None,
    evidence: DependencyProfileEnvironmentEvidence | None,
) -> (
    tuple[
        tuple[_ComparableInstalledDistribution, ...],
        Literal["independently_reconciled", "recomputed"],
    ]
    | DependencyEnvironmentDiagnosticNotEstablished
):
    try:
        observation = (
            observed_distributions
            if isinstance(
                observed_distributions,
                (
                    AmbientDependencyEnvironmentObservation,
                    ReceiptBackedDependencyEnvironmentObservation,
                ),
            )
            else _DEPENDENCY_ENVIRONMENT_OBSERVATION_ADAPTER.validate_python(
                observed_distributions
            )
        )
    except ValidationError:
        return _source_evidence_not_established(discriminant)
    if isinstance(observation, AmbientDependencyEnvironmentObservation):
        return (
            tuple(
                _ComparableInstalledDistribution(
                    name=canonicalize_name(row.name),
                    version=row.version,
                    source_kind=None,
                    selected_artifact=None,
                )
                for row in observation.distributions
            ),
            "independently_reconciled",
        )
    resolved = _resolve_receipt_backed_distributions(
        discriminant=discriminant,
        observation=observation,
        environment_root=environment_root,
        evidence=evidence,
    )
    if isinstance(resolved, DependencyEnvironmentDiagnosticNotEstablished):
        return resolved
    return resolved, "recomputed"


def _calculate_dependency_distribution_cases(
    *,
    discriminant: DependencyProfileDiscriminant,
    observations: tuple[_ComparableInstalledDistribution, ...],
    predicate_class: Literal["independently_reconciled", "recomputed"],
) -> tuple[DependencyEnvironmentDiagnosticCase, ...]:
    expected_by_name = {row.name: row for row in discriminant.resolved_distributions}
    observed_by_name: dict[str, list[_ComparableInstalledDistribution]] = {}
    for observation in observations:
        if observation.name in expected_by_name:
            observed_by_name.setdefault(observation.name, []).append(observation)

    root_cases: list[DependencyEnvironmentDiagnosticCase] = []
    missing_cases: list[DependencyEnvironmentDiagnosticCase] = []
    disagreement_cases: list[tuple[str, str, DependencyEnvironmentDiagnosticCase]] = []
    unexpected_cases: list[DependencyEnvironmentDiagnosticCase] = []
    root_name = canonicalize_name(discriminant.root_distribution)
    if root_name not in observed_by_name:
        root_cases.append(
            RootDistributionDiagnosticCase(
                case_kind="root_distribution_disagreement",
                coordinate="root_distribution",
                expected=root_name,
                observed="missing",
                predicate_class=predicate_class,
            )
        )

    for name in sorted(expected_by_name):
        matches = observed_by_name.get(name, [])
        expected = expected_by_name[name]
        if not matches:
            if name != root_name:
                missing_cases.append(
                    MissingDistributionDiagnosticCase(
                        case_kind="missing_resolved_distribution",
                        coordinate=f"distribution:{name}:missing",
                        expected=f"{expected.name}=={expected.version}",
                        observed="missing",
                        predicate_class=predicate_class,
                    )
                )
            continue
        if len(matches) != 1:
            unexpected_cases.append(
                UnexpectedInClosureIdentityDiagnosticCase(
                    case_kind="unexpected_in_closure_identity",
                    coordinate=f"distribution:{name}:identity",
                    expected="one_observation",
                    observed=f"{len(matches)}_observations",
                    predicate_class=predicate_class,
                )
            )
            continue
        observed = matches[0]
        comparisons: tuple[tuple[str, str, str], ...] = (
            ("version", expected.version, observed.version),
        )
        if observed.source_kind is not None:
            comparisons = (
                *comparisons,
                ("source_kind", expected.source_kind, observed.source_kind),
            )
        for field_name, expected_value, observed_value in comparisons:
            if expected_value != observed_value:
                case = DistributionFieldDiagnosticCase(
                    case_kind="distribution_field_disagreement",
                    coordinate=f"distribution:{name}:{field_name}",
                    field=field_name,
                    expected=expected_value,
                    observed=observed_value,
                    predicate_class=predicate_class,
                )
                disagreement_cases.append((name, field_name, case))
        if (
            observed.selected_artifact is not None
            and observed.selected_artifact != expected.selected_artifact
        ):
            case = DistributionFieldDiagnosticCase(
                case_kind="distribution_field_disagreement",
                coordinate=f"distribution:{name}:selected_artifact",
                field="selected_artifact",
                expected=expected.selected_artifact.value,
                observed=observed.selected_artifact.value,
                predicate_class=predicate_class,
            )
            disagreement_cases.append((name, "selected_artifact", case))

    return (
        *root_cases,
        *missing_cases,
        *(row[2] for row in sorted(disagreement_cases, key=lambda row: row[:2])),
        *unexpected_cases,
    )


def diagnose_dependency_environment(
    *,
    discriminant: DependencyProfileDiscriminant,
    observed_distributions: (
        DependencyEnvironmentObservation
        | Mapping[str, object]
        | Sequence[Mapping[str, object]]
    ),
    environment_root: Path | None = None,
    evidence: DependencyProfileEnvironmentEvidence | None = None,
) -> DependencyEnvironmentDiagnosticResult:
    """Diagnose installed coordinates without producing authority admission.

    Args:
        discriminant: Recomputed dependency-only expectation.
        observed_distributions: Explicit ambient or Foundry-receipt-backed
            observation. Legacy row sequences are unusable evidence.
        environment_root: Root whose retained marker resolves a receipt-backed
            observation. Ambient observations do not use it.
        evidence: Exact retained marker reader for a receipt-backed observation.

    Returns:
        A passing or failing non-decisive diagnostic, or a typed non-receipt
        when source-kind evidence needed for a pass is unavailable.
    """

    normalized = _normalize_distribution_observations(
        discriminant=discriminant,
        observed_distributions=observed_distributions,
        environment_root=environment_root,
        evidence=evidence,
    )
    if isinstance(normalized, DependencyEnvironmentDiagnosticNotEstablished):
        return normalized
    observations, predicate_class = normalized
    cases = _calculate_dependency_distribution_cases(
        discriminant=discriminant,
        observations=observations,
        predicate_class=predicate_class,
    )
    if cases:
        return DependencyEnvironmentDiagnosticFail(
            status="fail",
            ordered_cases=cases,
            first_case=cases[0],
            predicate_class=predicate_class,
        )
    if predicate_class == "independently_reconciled":
        return _source_evidence_not_established(discriminant)
    return DependencyEnvironmentDiagnosticPass(
        status="pass",
        ordered_cases=(),
        first_case=None,
        predicate_class="recomputed",
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


def _reopen_reconciled_environment_statement(
    *,
    environment_root: Path,
    environment_receipt: DependencyProfileEnvironmentReceipt,
    evidence: DependencyProfileEnvironmentEvidence,
) -> DependencyProfileEnvironmentStatement | AuthorityPredicateFailure:
    """Resolve one content-bound candidate receipt against retained marker bytes."""

    statement = environment_receipt.statement
    observed_receipt_ref = _environment_receipt_ref(statement)
    if observed_receipt_ref != environment_receipt.receipt_ref:
        return DigestPredicateMismatch(
            kind="digest_mismatch",
            predicate_id=AuthorityPredicateId.ENVIRONMENT_RECEIPT,
            code=AuthorityFailureCode.ENVIRONMENT_MISMATCH,
            expected=environment_receipt.receipt_ref.semantic_hash,
            observed=observed_receipt_ref.semantic_hash,
            predicate_class="recomputed",
        )
    reopened_marker = _reopen_bound_environment_marker(
        environment_root=environment_root,
        expected_marker_ref=statement.marker_ref,
        evidence=evidence,
    )
    if not isinstance(reopened_marker, DependencyEnvironmentMarkerStatement):
        return reopened_marker
    observed_statement = statement.model_copy(
        update={
            "stable_closure": reopened_marker.stable_closure,
            "python_runtime_installation_ref": (
                reopened_marker.python_runtime_installation_ref
            ),
            "python_runtime_verification_ref": (
                reopened_marker.python_runtime_verification_ref
            ),
            "instance_content_set": reopened_marker.instance_content_set,
        }
    )
    if observed_statement == statement:
        return statement
    observed_receipt_ref = record_ref(
        DigestDomain.ENVIRONMENT_RECEIPT,
        canonical_json_bytes(observed_statement.model_dump(mode="json")),
        schema_version=observed_statement.schema_version,
    )
    return DigestPredicateMismatch(
        kind="digest_mismatch",
        predicate_id=AuthorityPredicateId.ENVIRONMENT_RECEIPT,
        code=AuthorityFailureCode.ENVIRONMENT_MISMATCH,
        expected=environment_receipt.receipt_ref.semantic_hash,
        observed=observed_receipt_ref.semantic_hash,
        predicate_class="independently_reconciled",
    )


def reconcile_bound_installed_environment(
    profile: ResolvedMethodCatalogDependencyProfile,
    *,
    environment_root: Path,
    environment_receipt: DependencyProfileEnvironmentReceipt,
    evidence: DependencyProfileEnvironmentEvidence,
) -> DependencyProfileReconciliation:
    """Reopen the target marker and reconcile only the selected closure."""

    reopened_statement = _reopen_reconciled_environment_statement(
        environment_root=environment_root,
        environment_receipt=environment_receipt,
        evidence=evidence,
    )
    if not isinstance(reopened_statement, DependencyProfileEnvironmentStatement):
        return DependencyProfileReconciliationFail(
            status="fail",
            profile_id=profile.declaration.profile_id,
            failures=(reopened_statement,),
        )
    statement = reopened_statement
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
    "AmbientDependencyEnvironmentObservation",
    "DependencyEnvironmentDiagnosticCase",
    "DependencyEnvironmentDiagnosticFail",
    "DependencyEnvironmentDiagnosticNotEstablished",
    "DependencyEnvironmentDiagnosticPass",
    "DependencyEnvironmentDiagnosticResult",
    "DependencyEnvironmentObservation",
    "DependencyProfileDiscriminant",
    "DependencyProfileCandidateFailure",
    "DependencyProfileEnvironmentReceipt",
    "DependencyProfileInputMismatch",
    "DependencyProfileRegistryStatement",
    "InstalledDistributionObservation",
    "LockedDistributionIdentity",
    "MethodCatalogDependencyProfileDeclaration",
    "MethodCatalogProfileAdmission",
    "ObservedInstalledDistribution",
    "ProductionDataManifestInput",
    "ProductionDataManifestMissingFailure",
    "ProductionDataManifestPresent",
    "ProductionDataManifestUnavailable",
    "ReceiptBackedDependencyEnvironmentObservation",
    "ResolvedMethodCatalogDependencyProfile",
    "decode_dependency_profile_registry_toml",
    "declaration_ref",
    "diagnose_dependency_environment",
    "load_dependency_profile_registry",
    "observe_installed_distributions",
    "reconcile_bound_installed_environment",
    "resolve_dependency_discriminant",
    "resolve_dependency_profile",
    "resolve_profile_declaration",
    "resolve_profile_declaration_for_purpose",
    "read_candidate_production_data_manifest",
]
