"""Bound native observations of the environment used by an N5 execution.

The profile records observable interpreter, installed-distribution, selected
environment, declared-setting, and backend inputs. It is candidate identity
evidence only; it does not admit an institutional profile or custody external
authority.
"""

from __future__ import annotations

import math
import os
import platform
import sys
import sysconfig
import types
from collections import Counter
from importlib.machinery import EXTENSION_SUFFIXES, ModuleSpec
from itertools import islice
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Literal, Self

from packaging.utils import canonicalize_name
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common.canonical import CanonSpec, to_canonical_bytes
from polisyos.common.hashing import content_hash, streaming_hash

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from polisyos.runtime.quality.n5_execution_basis import N5ProductionImage

_MAX_DISTRIBUTIONS = 10_000
_MAX_SYS_PATH_ENTRIES = 256
_MAX_MODULES = 20_000
# A module can expose distinct spec-origin and __file__ paths. __cached__ is a
# hint and is excluded unless the bytecode path is itself an observed origin/file.
# Keep the finite image bound tied to the complete bounded module denominator.
_MAX_PROVIDER_PATHS_PER_MODULE = 2
_MAX_MODULE_FILES = _MAX_MODULES * _MAX_PROVIDER_PATHS_PER_MODULE + 1
_MAX_DECLARED_SETTINGS = 256
_MAX_TEXT_LENGTH = 4_096
_MAX_MODULE_FILE_BYTES = 256 * 1024 * 1024
_MAX_MODULE_IMAGE_BYTES = 2 * 1024 * 1024 * 1024
_MODULE_HASH_CHUNK_BYTES = 1024 * 1024
_CURRENT_BYTES_READ_LIMIT = 2 * 1024 * 1024 * 1024

type ProfileScalar = str | int | float | bool | None


def _safe_relative_identity(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        return False
    parts = path.parts
    if len(parts) >= 3 and parts[0] == "sys_path":
        index, *relative = parts[1:]
        return (
            index.isdecimal() and str(int(index)) == index and bool(relative) and relative != ["."]
        )
    if len(parts) >= 3 and parts[:2] == ("first_party", "polisyos"):
        return parts[-1].endswith(".py")
    if len(parts) >= 2 and parts[0] == "interpreter":
        suffix = PurePosixPath(*parts[1:])
        return (
            not suffix.is_absolute()
            and ".." not in suffix.parts
            and suffix.as_posix() == "/".join(parts[1:])
        )
    return False


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class N5ProfileSetting(_StrictModel):
    """One explicitly declared numerical or backend setting."""

    name: str = Field(min_length=1, max_length=128)
    value: ProfileScalar

    @model_validator(mode="after")
    def _supported_value(self) -> Self:
        if type(self.value) is float and not math.isfinite(self.value):
            raise ValueError("n5_execution_profile_setting_non_finite")
        if type(self.value) is str and len(self.value) > _MAX_TEXT_LENGTH:
            raise ValueError("n5_execution_profile_setting_too_long")
        return self


class N5InstalledDistribution(_StrictModel):
    """A retained row from the interpreter's complete metadata census."""

    normalized_name: str | None
    version: str | None
    metadata_location: str | None
    row_status: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _row_state_matches(self) -> Self:
        complete = all(
            value is not None
            for value in (self.normalized_name, self.version, self.metadata_location)
        )
        if complete != (self.row_status == "recomputed"):
            raise ValueError("n5_execution_profile_distribution_row_state_mismatch")
        if (self.row_status == "recomputed") == bool(self.reason_codes):
            raise ValueError("n5_execution_profile_distribution_reason_mismatch")
        return self


class N5EnvironmentValue(_StrictModel):
    """Current normalized value of one explicitly selected environment key."""

    name: Literal["FOUNDRY_SHAPE_CHECK", "POLISYOS_STRICT"]
    present: bool
    normalized_value: str | None
    observation: Literal["recomputed"] = "recomputed"

    @model_validator(mode="after")
    def _presence_matches_value(self) -> Self:
        if self.present != (self.normalized_value is not None):
            raise ValueError("n5_execution_profile_environment_presence_mismatch")
        return self


class N5BackendObservation(_StrictModel):
    """Typed result from the native backend API observer.

    Callers should construct this only from a native backend observation, not
    from a requested backend name or a user supplied profile label.
    """

    backend_name: str = Field(min_length=1, max_length=128)
    backend_version: str | None = Field(default=None, max_length=128)
    device_platforms: tuple[str, ...] = ()
    x64_enabled: bool | None = None
    numerical_policy: tuple[N5ProfileSetting, ...] = ()
    observation_provenance: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _backend_state_matches(self) -> Self:
        if (self.observation_provenance == "recomputed") == bool(self.reason_codes):
            raise ValueError("n5_execution_profile_backend_provenance_mismatch")
        if len({setting.name for setting in self.numerical_policy}) != len(self.numerical_policy):
            raise ValueError("n5_execution_profile_backend_setting_duplicate")
        return self


class N5LoadedModuleFileImage(_StrictModel):
    """One loaded file-backed module or interpreter image row."""

    relative_identity: str = Field(min_length=1, max_length=_MAX_TEXT_LENGTH)
    module_names: tuple[str, ...]
    file_kind: Literal[
        "python_source", "python_bytecode", "native_library", "other_file", "interpreter"
    ]
    coverage: Literal["streamed_file_bytes", "delegated_to_n5_production_image"]
    profile_scope: Literal["numerical_provider", "entrypoint", "interpreter"]
    byte_length: int | None = Field(default=None, ge=0)
    content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    row_status: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _file_image_state(self) -> Self:
        if not _safe_relative_identity(self.relative_identity):
            raise ValueError("n5_loaded_module_relative_identity_invalid")
        streamed = self.coverage == "streamed_file_bytes"
        if streamed:
            complete = self.byte_length is not None and self.content_hash is not None
            if complete != (self.row_status == "recomputed"):
                raise ValueError("n5_loaded_module_file_state_mismatch")
        elif self.byte_length is not None or self.content_hash is not None:
            raise ValueError("n5_loaded_module_delegated_image_has_bytes")
        if (self.row_status == "recomputed") == bool(self.reason_codes):
            raise ValueError("n5_loaded_module_file_reason_mismatch")
        if self.module_names != tuple(sorted(set(self.module_names))):
            raise ValueError("n5_loaded_module_names_invalid")
        if (self.file_kind == "interpreter") != (self.profile_scope == "interpreter"):
            raise ValueError("n5_loaded_module_interpreter_scope_mismatch")
        if self.coverage == "delegated_to_n5_production_image" and (
            not self.relative_identity.startswith("first_party/polisyos/")
            or self.file_kind != "python_source"
        ):
            raise ValueError("n5_loaded_module_delegated_scope_invalid")
        return self


class N5LoadedModuleObservation(_StrictModel):
    """One bounded census of the current interpreter's loaded modules."""

    schema_version: Literal["N5LoadedModuleObservation@1.0"] = "N5LoadedModuleObservation@1.0"
    loaded_module_count: int = Field(ge=0, le=_MAX_MODULES)
    file_images: tuple[N5LoadedModuleFileImage, ...]
    built_in_modules: tuple[str, ...] = ()
    frozen_modules: tuple[str, ...] = ()
    namespace_modules: tuple[str, ...] = ()
    no_file_modules: tuple[str, ...] = ()
    dynamic_modules: tuple[str, ...] = ()
    unclassified_modules: tuple[str, ...] = ()
    entrypoint_modules: tuple[str, ...] = ()
    census_predicate: Literal["recomputed", "not_established"]
    file_backed_bytes_predicate: Literal["recomputed", "not_established"]
    first_party_coverage: Literal["delegated_to_n5_production_image"] = (
        "delegated_to_n5_production_image"
    )
    source_code_association_predicate: Literal["not_established"] = "not_established"
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _census_state(self) -> Self:
        categories = (
            self.built_in_modules,
            self.frozen_modules,
            self.namespace_modules,
            self.no_file_modules,
            self.dynamic_modules,
            self.unclassified_modules,
            self.entrypoint_modules,
        )
        if any(names != tuple(sorted(set(names))) for names in categories):
            raise ValueError("n5_loaded_module_categories_invalid")
        interpreter_rows = tuple(row for row in self.file_images if row.file_kind == "interpreter")
        interpreter_image_complete = (
            len(interpreter_rows) == 1 and interpreter_rows[0].row_status == "recomputed"
        )
        expected_census: Literal["recomputed", "not_established"] = (
            "not_established"
            if not interpreter_image_complete
            or self.reason_codes
            or any(row.row_status == "not_established" for row in self.file_images)
            else "recomputed"
        )
        expected_files: Literal["recomputed", "not_established"] = (
            "not_established"
            if not interpreter_image_complete
            or self.reason_codes
            or any(row.row_status == "not_established" for row in self.file_images)
            else "recomputed"
        )
        if (
            self.census_predicate != expected_census
            or self.file_backed_bytes_predicate != expected_files
            or (expected_census == "recomputed") == bool(self.reason_codes)
        ):
            raise ValueError("n5_loaded_module_predicate_mismatch")
        if len(self.file_images) > _MAX_MODULE_FILES:
            raise ValueError("n5_loaded_module_file_denominator_over_limit")
        observed_names = {
            *self.built_in_modules,
            *self.frozen_modules,
            *self.namespace_modules,
            *self.no_file_modules,
            *self.dynamic_modules,
            *self.unclassified_modules,
            *(
                name
                for row in self.file_images
                for name in row.module_names
                if name != "<interpreter>"
            ),
        }
        if (
            not any(name.startswith("<") for name in self.unclassified_modules)
            and len(observed_names) != self.loaded_module_count
        ):
            raise ValueError("n5_loaded_module_denominator_mismatch")
        return self


class N5NativeExecutionProfile(_StrictModel):
    """Immutable content-bound observation for candidate N5 identity checks."""

    schema_version: Literal["N5NativeExecutionProfile@1.0"] = "N5NativeExecutionProfile@1.0"
    authority_purpose: Literal["candidate_execution_identity_only"] = (
        "candidate_execution_identity_only"
    )
    interpreter: tuple[tuple[str, str], ...]
    platform_identity: tuple[tuple[str, str], ...]
    sys_path: tuple[str, ...]
    sys_path_status: Literal["recomputed", "not_established"]
    distributions: tuple[N5InstalledDistribution, ...]
    distribution_census_status: Literal["recomputed", "not_established"]
    selected_environment: tuple[N5EnvironmentValue, ...]
    declared_settings: tuple[N5ProfileSetting, ...]
    loaded_module_observation: N5LoadedModuleObservation
    backend_observation: N5BackendObservation | None = None
    interpreter_platform_predicate: Literal["recomputed", "not_established"]
    distribution_predicate: Literal["recomputed", "not_established"]
    loaded_module_predicate: Literal["recomputed", "not_established"]
    file_backed_module_bytes_predicate: Literal["recomputed", "not_established"]
    first_party_source_image_predicate: Literal["delegated_to_n5_production_image"] = (
        "delegated_to_n5_production_image"
    )
    source_code_association_predicate: Literal["not_established"] = "not_established"
    backend_predicate: Literal["recomputed", "not_established"]
    profile_identity_predicate: Literal["recomputed", "not_established"]
    institutional_profile_admission: Literal["not_established"] = "not_established"
    reason_codes: tuple[str, ...] = ()
    numerical_profile_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_profile(self) -> Self:
        expected_path_status: Literal["recomputed", "not_established"] = (
            "recomputed"
            if self.sys_path and len(self.sys_path) <= _MAX_SYS_PATH_ENTRIES
            else "not_established"
        )
        expected_interpreter_status: Literal["recomputed", "not_established"] = (
            "recomputed"
            if self.interpreter and self.platform_identity and self.sys_path_status == "recomputed"
            else "not_established"
        )
        expected_distribution_status: Literal["recomputed", "not_established"] = (
            "recomputed"
            if self.distributions
            and len(self.distributions) <= _MAX_DISTRIBUTIONS
            and all(row.row_status == "recomputed" for row in self.distributions)
            and _distribution_ambiguities(self.distributions) == ()
            else "not_established"
        )
        expected_backend_status: Literal["recomputed", "not_established"] = (
            "recomputed"
            if self.backend_observation is not None
            and self.backend_observation.observation_provenance == "recomputed"
            else "not_established"
        )
        expected_module_status = self.loaded_module_observation.census_predicate
        expected_file_status = self.loaded_module_observation.file_backed_bytes_predicate
        expected_identity_status: Literal["recomputed", "not_established"] = (
            "recomputed"
            if expected_interpreter_status == "recomputed"
            and expected_distribution_status == "recomputed"
            and expected_module_status == "recomputed"
            and expected_file_status == "recomputed"
            and expected_backend_status == "recomputed"
            else "not_established"
        )
        if (
            self.sys_path_status != expected_path_status
            or self.interpreter_platform_predicate != expected_interpreter_status
            or self.distribution_census_status != expected_distribution_status
            or self.distribution_predicate != expected_distribution_status
            or self.loaded_module_predicate != expected_module_status
            or self.file_backed_module_bytes_predicate != expected_file_status
            or self.backend_predicate != expected_backend_status
            or self.profile_identity_predicate != expected_identity_status
        ):
            raise ValueError("n5_execution_profile_predicate_mismatch")
        expected_reasons = _profile_reasons(
            sys_path_status=expected_path_status,
            distributions=self.distributions,
            distribution_status=expected_distribution_status,
            module_status=expected_module_status,
            backend_status=expected_backend_status,
        )
        if self.reason_codes != expected_reasons:
            raise ValueError("n5_execution_profile_reason_mismatch")
        if len({setting.name for setting in self.declared_settings}) != len(self.declared_settings):
            raise ValueError("n5_execution_profile_setting_duplicate")
        payload = self.model_dump(
            mode="json", exclude={"content_hash", "numerical_profile_content_hash"}
        )
        if self.content_hash != _profile_hash(payload):
            raise ValueError("n5_execution_profile_content_mismatch")
        if self.numerical_profile_content_hash != _numerical_profile_content_hash(self):
            raise ValueError("n5_execution_profile_identity_content_mismatch")
        return self


class N5ProfileContentComparison(_StrictModel):
    """Pure comparison of a recorded profile against a fresh observation."""

    schema_version: Literal["N5ProfileContentComparison@1.0"] = "N5ProfileContentComparison@1.0"
    status: Literal["recomputed", "changed", "not_established"]
    recorded_numerical_profile_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    current_numerical_profile_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    matched_provider_identities: tuple[str, ...] = ()
    missing_provider_identities: tuple[str, ...] = ()
    changed_provider_identities: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _comparison_state(self) -> Self:
        if any(
            identities != tuple(sorted(set(identities)))
            for identities in (
                self.matched_provider_identities,
                self.missing_provider_identities,
                self.changed_provider_identities,
                self.reason_codes,
            )
        ):
            raise ValueError("n5_profile_comparison_rows_invalid")
        if self.status == "recomputed":
            expected = (
                not self.reason_codes
                and not self.missing_provider_identities
                and not self.changed_provider_identities
            )
        elif self.status == "changed":
            expected = (
                bool(self.changed_provider_identities)
                or "profile_content_changed" in self.reason_codes
            )
        else:
            expected = bool(self.reason_codes) or bool(self.missing_provider_identities)
        if not expected:
            raise ValueError("n5_profile_comparison_state_mismatch")
        return self


def observe_n5_native_execution_profile(
    *,
    first_party_root: Path,
    declared_settings: Mapping[str, ProfileScalar] | None = None,
    operational_settings: Mapping[str, ProfileScalar] | None = None,
    entrypoint_module_names: tuple[str, ...] = (),
) -> N5NativeExecutionProfile:
    """Observe the current interpreter, installed distributions, and selected env.

    Args:
        first_party_root: Package source root covered separately by the enclosing
            ``N5ProductionImage``. The native profile records only its relative
            scope and does not bind that image's content hash.
        declared_settings: Explicit numerical/backend settings consumed by the
            caller's execution plan. These remain declared inputs, not native
            observations or institutional profile admission.
        operational_settings: Explicit execution controls such as quota or
            reservation values. Accepted for clarity and deliberately excluded
            from the profile identity.
        entrypoint_module_names: Explicit host or harness entrypoint module
            names. Their file images remain in the full observation, while
            their execution role is retained as a declared closure residual.

    Returns:
        A strict immutable profile. Missing, ambiguous, duplicate, or over-limit
        metadata is retained as a typed ``not_established`` result.
    """
    from importlib import metadata

    settings = _settings_rows(declared_settings or {})
    _validate_settings(operational_settings or {})
    module_observation = _observe_loaded_module_images(
        first_party_root=first_party_root,
        entrypoint_module_names=entrypoint_module_names,
    )
    try:
        distributions = metadata.distributions()
    except Exception:
        distributions = ()
        census_available = False
    else:
        census_available = True
    rows, census_complete = _observe_distributions(distributions)
    census_complete = census_complete and census_available
    if not census_complete:
        rows = rows[:_MAX_DISTRIBUTIONS]
    duplicate_reasons = _distribution_ambiguities(rows)
    distribution_status: Literal["recomputed", "not_established"] = (
        "recomputed"
        if census_complete
        and rows
        and all(row.row_status == "recomputed" for row in rows)
        and not duplicate_reasons
        else "not_established"
    )
    path, path_status = _observe_sys_path()
    interpreter = (
        ("implementation", sys.implementation.name),
        ("version", sys.version.split()[0]),
        ("cache_tag", sys.implementation.cache_tag or ""),
        ("soabi", str(sysconfig.get_config_var("SOABI") or "")),
    )
    platform_identity = (
        ("sys_platform", sys.platform),
        ("system", platform.system()),
        ("release", platform.release()),
        ("machine", platform.machine()),
        ("architecture", platform.architecture()[0]),
    )
    environment = tuple(
        _observe_environment(name) for name in ("FOUNDRY_SHAPE_CHECK", "POLISYOS_STRICT")
    )
    return _build_profile(
        interpreter=interpreter,
        platform_identity=platform_identity,
        sys_path=path,
        sys_path_status=path_status,
        distributions=tuple(rows),
        distribution_status=distribution_status,
        selected_environment=environment,
        declared_settings=settings,
        loaded_module_observation=module_observation,
        backend_observation=None,
    )


def bind_n5_backend_observation(
    profile: N5NativeExecutionProfile,
    observation: N5BackendObservation,
) -> N5NativeExecutionProfile:
    """Bind a separately observed backend result and recompute profile identity.

    This function records the supplied typed result. It does not verify that a
    backend API was called, confer authority, or treat a requested backend as
    an observation.

    Args:
        profile: Native environment profile returned by this module.
        observation: Typed result from the execution bridge's native backend API.

    Returns:
        A new immutable profile with content hash recomputed.
    """
    if type(profile) is not N5NativeExecutionProfile:
        raise TypeError("n5_execution_profile_type_invalid")
    if type(observation) is not N5BackendObservation:
        raise TypeError("n5_backend_observation_type_invalid")
    return _build_profile(
        interpreter=profile.interpreter,
        platform_identity=profile.platform_identity,
        sys_path=profile.sys_path,
        sys_path_status=profile.sys_path_status,
        distributions=profile.distributions,
        distribution_status=profile.distribution_census_status,
        selected_environment=profile.selected_environment,
        declared_settings=profile.declared_settings,
        loaded_module_observation=profile.loaded_module_observation,
        backend_observation=observation,
    )


def _settings_rows(settings: Mapping[str, ProfileScalar]) -> tuple[N5ProfileSetting, ...]:
    _validate_settings(settings)
    rows: list[N5ProfileSetting] = []
    for name, value in settings.items():
        rows.append(N5ProfileSetting(name=name, value=value))
    return tuple(sorted(rows, key=lambda row: row.name))


def _validate_settings(settings: Mapping[str, ProfileScalar]) -> None:
    if len(settings) > _MAX_DECLARED_SETTINGS:
        raise ValueError("n5_execution_profile_settings_over_limit")
    for name, value in settings.items():
        if type(name) is not str or not name or len(name) > 128:
            raise ValueError("n5_execution_profile_setting_name_invalid")
        if value is not None and type(value) not in {str, int, float, bool}:
            raise ValueError("n5_execution_profile_setting_value_invalid")
        if type(value) is str and len(value) > _MAX_TEXT_LENGTH:
            raise ValueError("n5_execution_profile_setting_value_too_long")
        if type(value) is float and not math.isfinite(value):
            raise ValueError("n5_execution_profile_setting_non_finite")


def _observe_distributions(
    distributions: Iterable[object],
) -> tuple[list[N5InstalledDistribution], bool]:
    rows: list[N5InstalledDistribution] = []
    complete = True
    try:
        for index, distribution in enumerate(distributions):
            if index >= _MAX_DISTRIBUTIONS:
                complete = False
                break
            rows.append(_distribution_row(distribution))
    except Exception:
        complete = False
    rows.sort(
        key=lambda row: (
            row.normalized_name or "",
            row.version or "",
            row.metadata_location or "",
            row.reason_codes,
        )
    )
    return rows, complete


def _observe_loaded_module_images(
    *,
    first_party_root: Path,
    modules: Mapping[str, object] | None = None,
    sys_path: Sequence[str] | None = None,
    interpreter_path: str | None = None,
    entrypoint_module_names: tuple[str, ...] = (),
) -> N5LoadedModuleObservation:
    """Observe loaded module origins and stream file-backed provider bytes once."""
    raw_modules = sys.modules if modules is None else modules
    raw_sys_path = sys.path if sys_path is None else sys_path
    raw_interpreter_path = sys.executable if interpreter_path is None else interpreter_path
    reasons: set[str] = set()
    built_in: list[str] = []
    frozen: list[str] = []
    namespaces: list[str] = []
    no_file: list[str] = []
    dynamic: list[str] = []
    unclassified: list[str] = []
    entrypoints: list[str] = []
    grouped: dict[
        Path,
        tuple[
            str,
            set[str],
            Literal[
                "python_source",
                "python_bytecode",
                "native_library",
                "other_file",
                "interpreter",
            ],
            str,
        ],
    ] = {}
    first_party: Path | None
    try:
        if not isinstance(first_party_root, Path) or first_party_root.name != "polisyos":
            raise ValueError("first_party_root_invalid")
        first_party = first_party_root.resolve(strict=True)
        if first_party_root.is_symlink() or not first_party.is_dir():
            raise ValueError("first_party_root_not_directory")
    except (OSError, RuntimeError, TypeError, ValueError):
        first_party = None
        reasons.add("first_party_root_not_established")

    import_roots: list[Path] = []
    if len(raw_sys_path) > _MAX_SYS_PATH_ENTRIES:
        reasons.add("loaded_module_sys_path_over_limit")
    for entry in raw_sys_path[:_MAX_SYS_PATH_ENTRIES]:
        if type(entry) is not str or len(entry) > _MAX_TEXT_LENGTH:
            continue
        try:
            root = Path(entry or os.curdir).resolve()
        except (OSError, RuntimeError, TypeError, ValueError):
            continue
        if root not in import_roots:
            import_roots.append(root)

    try:
        if len(raw_modules) > _MAX_MODULES:
            reasons.add("loaded_module_denominator_over_limit")
            module_items = tuple(islice(raw_modules.items(), _MAX_MODULES))
            unclassified.append("<module-denominator-over-limit>")
        else:
            module_items = tuple(raw_modules.items())
    except Exception:
        module_items = ()
        unclassified.append("<module-table-unreadable>")
        reasons.add("loaded_module_table_unreadable")

    entrypoint_names_valid = (
        type(entrypoint_module_names) is tuple
        and len(entrypoint_module_names) <= _MAX_MODULES
        and all(type(name) is str and name and len(name) <= 512 for name in entrypoint_module_names)
        and len(set(entrypoint_module_names)) == len(entrypoint_module_names)
    )
    if not entrypoint_names_valid:
        reasons.add("entrypoint_module_scope_invalid")
    explicit_entrypoints = set(entrypoint_module_names) if entrypoint_names_valid else set()
    observed_module_names = {name for name, _module in module_items if type(name) is str and name}
    if explicit_entrypoints - observed_module_names:
        reasons.add("entrypoint_module_not_loaded")

    for name, module in module_items:
        if type(name) is not str or not name or len(name) > 512:
            unclassified.append("<module-name-invalid>")
            reasons.add("loaded_module_name_not_established")
            continue
        is_entrypoint = name in explicit_entrypoints
        if is_entrypoint:
            entrypoints.append(name)
        if module is None:
            no_file.append(name)
            continue
        if not isinstance(module, types.ModuleType):
            unclassified.append(name)
            continue
        try:
            namespace = types.ModuleType.__getattribute__(module, "__dict__")
        except (AttributeError, TypeError, ValueError):
            unclassified.append(name)
            continue
        if type(namespace) is not dict:
            unclassified.append(name)
            continue
        spec = namespace.get("__spec__")
        if spec is not None and type(spec) is not ModuleSpec:
            unclassified.append(name)
            spec = None
        try:
            origin = spec.origin if spec is not None else None
        except (AttributeError, TypeError, ValueError):
            origin = None
        if type(origin) is str and origin == "built-in":
            built_in.append(name)
            continue
        if type(origin) is str and origin == "frozen":
            frozen.append(name)
            continue
        if origin is None:
            try:
                namespace_locations = (
                    spec.submodule_search_locations is not None if spec is not None else False
                )
            except (AttributeError, TypeError, ValueError):
                namespace_locations = False
            if namespace_locations:
                namespaces.append(name)
            elif not any(namespace.get(key) is not None for key in ("__file__", "__cached__")):
                no_file.append(name)
            else:
                dynamic.append(name)
        else:
            if (
                type(origin) is not str
                or not origin
                or origin.startswith("<")
                or not Path(origin).is_absolute()
            ):
                dynamic.append(name)
        raw_paths: list[tuple[str, bool]] = []
        if type(origin) is str and origin and not origin.startswith("<"):
            raw_paths.append((origin, True))
        file_path_value = namespace.get("__file__")
        if (
            type(file_path_value) is str
            and file_path_value
            and file_path_value not in {path for path, _required in raw_paths}
            and not file_path_value.startswith("<")
        ):
            raw_paths.append((file_path_value, True))
        if not raw_paths:
            if (
                origin is not None
                and not (type(origin) is str and origin in ("built-in", "frozen"))
                and name not in dynamic
            ):
                unclassified.append(name)
            continue
        file_paths: set[Path] = set()
        for raw_path, required in raw_paths:
            if not Path(raw_path).is_absolute():
                if required:
                    reasons.add("loaded_module_file_bytes_not_established")
                continue
            try:
                candidate = Path(raw_path).resolve(strict=True)
                if candidate.is_file():
                    file_paths.add(candidate)
                elif required:
                    reasons.add("loaded_module_file_bytes_not_established")
            except (OSError, RuntimeError, TypeError, ValueError):
                if required:
                    reasons.add("loaded_module_file_bytes_not_established")
        if not file_paths:
            if name not in dynamic:
                unclassified.append(name)
            if any(required for _raw_path, required in raw_paths):
                reasons.add("loaded_module_file_bytes_not_established")
            continue
        origin_recorded = type(origin) is str and any(
            path == origin for path, _required in raw_paths
        )
        if (origin is None or not origin_recorded) and name not in dynamic:
            dynamic.append(name)
        for file_path in file_paths:
            file_kind = _module_file_kind(file_path) or "other_file"
            coverage = "streamed_file_bytes"
            identity: str | None
            if file_kind == "python_source" and first_party is not None:
                try:
                    relative = file_path.relative_to(first_party).as_posix()
                except ValueError:
                    relative = None
                if relative is not None:
                    identity = f"first_party/polisyos/{relative}"
                    coverage = "delegated_to_n5_production_image"
                else:
                    identity = _sys_path_relative_identity(file_path, import_roots)
            else:
                identity = _sys_path_relative_identity(file_path, import_roots)
            if identity is None:
                unclassified.append(name)
                reasons.add("loaded_module_relative_identity_not_established")
                continue
            if len(identity) > _MAX_TEXT_LENGTH:
                unclassified.append(name)
                reasons.add("loaded_module_relative_identity_not_established")
                continue
            old = grouped.get(file_path)
            names = old[1] if old is not None else set()
            names.add(name)
            grouped[file_path] = (coverage, names, file_kind, identity)

    file_rows: list[N5LoadedModuleFileImage] = []
    total_bytes = 0
    if len(grouped) > _MAX_MODULE_FILES - 1:
        reasons.add("loaded_module_file_denominator_over_limit")
    for file_path, (coverage, module_names, file_kind, identity) in sorted(
        grouped.items(), key=lambda item: item[1][3]
    )[: _MAX_MODULE_FILES - 1]:
        if coverage == "delegated_to_n5_production_image":
            file_rows.append(
                N5LoadedModuleFileImage(
                    relative_identity=identity,
                    module_names=tuple(sorted(module_names)),
                    file_kind=file_kind,
                    coverage=coverage,
                    profile_scope=(
                        "entrypoint"
                        if module_names and module_names.issubset(explicit_entrypoints)
                        else "numerical_provider"
                    ),
                    row_status="recomputed",
                )
            )
            continue
        remaining_bytes = _MAX_MODULE_IMAGE_BYTES - total_bytes
        result = _stream_file_image(file_path, remaining_bytes=remaining_bytes)
        if result is None:
            file_rows.append(
                N5LoadedModuleFileImage(
                    relative_identity=identity,
                    module_names=tuple(sorted(module_names)),
                    file_kind=file_kind,
                    coverage="streamed_file_bytes",
                    profile_scope=(
                        "entrypoint"
                        if module_names and module_names.issubset(explicit_entrypoints)
                        else "numerical_provider"
                    ),
                    row_status="not_established",
                    reason_codes=("loaded_module_file_unreadable_or_over_budget",),
                )
            )
            reasons.add("loaded_module_file_bytes_not_established")
            continue
        byte_length, digest = result
        total_bytes += byte_length
        file_rows.append(
            N5LoadedModuleFileImage(
                relative_identity=identity,
                module_names=tuple(sorted(module_names)),
                file_kind=file_kind,
                coverage="streamed_file_bytes",
                profile_scope=(
                    "entrypoint"
                    if module_names and module_names.issubset(explicit_entrypoints)
                    else "numerical_provider"
                ),
                byte_length=byte_length,
                content_hash=digest,
                row_status="recomputed",
            )
        )

    interpreter_result = _interpreter_image_identity(raw_interpreter_path, import_roots)
    if interpreter_result is None:
        reasons.add("interpreter_binary_not_established")
        unclassified.append("<interpreter>")
    else:
        interpreter_path_obj, interpreter_identity = interpreter_result
        result = _stream_file_image(
            interpreter_path_obj,
            remaining_bytes=_MAX_MODULE_IMAGE_BYTES - total_bytes,
        )
        if result is None:
            reasons.add("interpreter_binary_bytes_not_established")
            file_rows.append(
                N5LoadedModuleFileImage(
                    relative_identity=interpreter_identity,
                    module_names=("<interpreter>",),
                    file_kind="interpreter",
                    coverage="streamed_file_bytes",
                    profile_scope="interpreter",
                    row_status="not_established",
                    reason_codes=("interpreter_binary_unreadable_or_over_budget",),
                )
            )
        else:
            byte_length, digest = result
            file_rows.append(
                N5LoadedModuleFileImage(
                    relative_identity=interpreter_identity,
                    module_names=("<interpreter>",),
                    file_kind="interpreter",
                    coverage="streamed_file_bytes",
                    profile_scope="interpreter",
                    byte_length=byte_length,
                    content_hash=digest,
                    row_status="recomputed",
                )
            )

    if len(grouped) > _MAX_MODULE_FILES - 1:
        unclassified.append("<module-file-denominator-over-limit>")
    built_in_tuple = tuple(sorted(built_in))
    frozen_tuple = tuple(sorted(frozen))
    namespace_tuple = tuple(sorted(namespaces))
    no_file_tuple = tuple(sorted(no_file))
    dynamic_tuple = tuple(sorted(dynamic))
    unclassified_tuple = tuple(sorted(set(unclassified)))
    incomplete = bool(reasons or any(row.row_status == "not_established" for row in file_rows))
    census_status: Literal["recomputed", "not_established"] = (
        "not_established" if incomplete else "recomputed"
    )
    file_status: Literal["recomputed", "not_established"] = (
        "not_established"
        if reasons or any(row.row_status == "not_established" for row in file_rows)
        else "recomputed"
    )
    return N5LoadedModuleObservation(
        loaded_module_count=min(len(raw_modules), _MAX_MODULES),
        file_images=tuple(sorted(file_rows, key=lambda row: row.relative_identity)),
        built_in_modules=built_in_tuple,
        frozen_modules=frozen_tuple,
        namespace_modules=namespace_tuple,
        no_file_modules=no_file_tuple,
        dynamic_modules=dynamic_tuple,
        unclassified_modules=unclassified_tuple,
        entrypoint_modules=tuple(sorted(set(entrypoints))),
        census_predicate=census_status,
        file_backed_bytes_predicate=file_status,
        reason_codes=tuple(sorted(reasons)),
    )


def _module_file_kind(
    path: Path,
) -> Literal["python_source", "python_bytecode", "native_library"] | None:
    name = path.name
    if name.endswith(".py"):
        return "python_source"
    if name.endswith(".pyc"):
        return "python_bytecode"
    if any(name.endswith(suffix) for suffix in EXTENSION_SUFFIXES):
        return "native_library"
    return None


def _sys_path_relative_identity(path: Path, roots: list[Path]) -> str | None:
    matches: list[tuple[int, int, str]] = []
    for index, root in enumerate(roots):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        identity = f"sys_path/{index}/{relative.as_posix()}"
        if len(identity) <= _MAX_TEXT_LENGTH:
            matches.append((len(root.parts), -index, identity))
    if not matches:
        return None
    return max(matches)[2]


def _interpreter_image_identity(
    raw_path: str,
    roots: list[Path],
) -> tuple[Path, str] | None:
    if type(raw_path) is not str or not raw_path or len(raw_path) > _MAX_TEXT_LENGTH:
        return None
    try:
        path = Path(raw_path).resolve(strict=True)
        if not path.is_file():
            return None
        prefix_candidates = (Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve())
        for prefix in prefix_candidates:
            try:
                relative = path.relative_to(prefix)
            except ValueError:
                continue
            return path, f"interpreter/{relative.as_posix()}"
        identity = _sys_path_relative_identity(path, roots)
        if identity is not None:
            return path, f"interpreter/{identity}"
    except (OSError, RuntimeError, TypeError, ValueError):
        return None
    return None


def _stream_file_image(path: Path, *, remaining_bytes: int) -> tuple[int, str] | None:
    """Hash stable file bytes in bounded chunks without retaining file content."""
    try:
        before = path.stat()
        if (
            not path.is_file()
            or before.st_size < 0
            or before.st_size > _MAX_MODULE_FILE_BYTES
            or before.st_size > remaining_bytes
        ):
            return None
        count = 0
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_size) != (
                before.st_dev,
                before.st_ino,
                before.st_size,
            ):
                return None
            opened_mtime_ns = getattr(opened, "st_mtime_ns", None)
            opened_ctime_ns = getattr(opened, "st_ctime_ns", None)

            def chunks() -> Iterable[bytes]:
                nonlocal count
                while True:
                    block = handle.read(_MODULE_HASH_CHUNK_BYTES)
                    if not block:
                        break
                    count += len(block)
                    if (
                        count > before.st_size
                        or count > _MAX_MODULE_FILE_BYTES
                        or count > remaining_bytes
                    ):
                        raise ValueError("n5_loaded_module_file_grew_or_over_budget")
                    yield block

            digest = streaming_hash(chunks(), prefix=True)
            after = os.fstat(handle.fileno())
        if (
            count != before.st_size
            or (after.st_dev, after.st_ino, after.st_size)
            != (opened.st_dev, opened.st_ino, opened.st_size)
            or getattr(after, "st_mtime_ns", None) != opened_mtime_ns
            or getattr(after, "st_ctime_ns", None) != opened_ctime_ns
        ):
            return None
        return count, digest
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def _distribution_row(distribution: object) -> N5InstalledDistribution:
    reasons: list[str] = []
    name: str | None = None
    version: str | None = None
    location: str | None = None
    try:
        raw_name = distribution.metadata.get("Name")  # type: ignore[attr-defined]
        if type(raw_name) is str and raw_name.strip():
            normalized = canonicalize_name(raw_name.strip())
            if normalized:
                name = normalized
            else:
                reasons.append("distribution_name_invalid")
        else:
            reasons.append("distribution_name_missing")
    except Exception:
        reasons.append("distribution_metadata_unreadable")
    try:
        raw_version = distribution.version  # type: ignore[attr-defined]
        if type(raw_version) is str and raw_version.strip():
            version = raw_version.strip()
        else:
            reasons.append("distribution_version_missing")
    except Exception:
        reasons.append("distribution_version_unreadable")
    try:
        raw_location = getattr(distribution, "_path", None)
        if isinstance(raw_location, (str, os.PathLike)):
            metadata_path = Path(raw_location).resolve(strict=True)
            if metadata_path.is_dir():
                location = str(metadata_path)
            else:
                reasons.append("distribution_metadata_location_not_directory")
        else:
            reasons.append("distribution_metadata_location_missing")
    except (OSError, RuntimeError, TypeError, ValueError):
        reasons.append("distribution_metadata_location_unreadable")
    if any(value is None for value in (name, version, location)) and not reasons:
        reasons.append("distribution_identity_incomplete")
    if location is not None and len(location) > _MAX_TEXT_LENGTH:
        location = None
        reasons.append("distribution_metadata_location_too_long")
    status: Literal["recomputed", "not_established"] = (
        "recomputed"
        if name is not None and version is not None and location is not None
        else "not_established"
    )
    return N5InstalledDistribution(
        normalized_name=name,
        version=version,
        metadata_location=location,
        row_status=status,
        reason_codes=tuple(sorted(set(reasons))),
    )


def _observe_sys_path() -> tuple[tuple[str, ...], Literal["recomputed", "not_established"]]:
    if len(sys.path) > _MAX_SYS_PATH_ENTRIES:
        return (), "not_established"
    paths: list[str] = []
    try:
        for entry in sys.path:
            if type(entry) is not str or len(entry) > _MAX_TEXT_LENGTH:
                return (), "not_established"
            paths.append(str(Path(entry or os.curdir).resolve()))
    except (OSError, RuntimeError, TypeError, ValueError):
        return (), "not_established"
    return tuple(paths), "recomputed" if paths else "not_established"


def _observe_environment(
    name: Literal["FOUNDRY_SHAPE_CHECK", "POLISYOS_STRICT"],
) -> N5EnvironmentValue:
    raw = os.environ.get(name)
    normalized = raw.strip().lower() if raw is not None else None
    return N5EnvironmentValue(
        name=name,
        present=raw is not None,
        normalized_value=normalized,
    )


def _distribution_ambiguities(
    rows: tuple[N5InstalledDistribution, ...] | list[N5InstalledDistribution],
) -> tuple[str, ...]:
    names = [row.normalized_name for row in rows if row.normalized_name is not None]
    locations = [row.metadata_location for row in rows if row.metadata_location is not None]
    reasons: list[str] = []
    if any(count > 1 for count in Counter(names).values()):
        reasons.append("distribution_name_ambiguous")
    if any(count > 1 for count in Counter(locations).values()):
        reasons.append("distribution_location_ambiguous")
    return tuple(reasons)


def _profile_reasons(
    *,
    sys_path_status: Literal["recomputed", "not_established"],
    distributions: tuple[N5InstalledDistribution, ...],
    distribution_status: Literal["recomputed", "not_established"],
    module_status: Literal["recomputed", "not_established"],
    backend_status: Literal["recomputed", "not_established"],
) -> tuple[str, ...]:
    reasons: set[str] = set()
    if sys_path_status != "recomputed":
        reasons.add("sys_path_observation_incomplete")
    if distribution_status != "recomputed":
        reasons.add("distribution_census_not_established")
    reasons.update(_distribution_ambiguities(distributions))
    for row in distributions:
        reasons.update(row.reason_codes)
    if module_status != "recomputed":
        reasons.add("loaded_module_census_not_established")
    if backend_status != "recomputed":
        reasons.add("backend_observation_not_established")
    return tuple(sorted(reasons))


def _build_profile(
    *,
    interpreter: tuple[tuple[str, str], ...],
    platform_identity: tuple[tuple[str, str], ...],
    sys_path: tuple[str, ...],
    sys_path_status: Literal["recomputed", "not_established"],
    distributions: tuple[N5InstalledDistribution, ...],
    distribution_status: Literal["recomputed", "not_established"],
    selected_environment: tuple[N5EnvironmentValue, ...],
    declared_settings: tuple[N5ProfileSetting, ...],
    loaded_module_observation: N5LoadedModuleObservation,
    backend_observation: N5BackendObservation | None,
) -> N5NativeExecutionProfile:
    interpreter_status: Literal["recomputed", "not_established"] = (
        "recomputed"
        if interpreter and platform_identity and sys_path_status == "recomputed"
        else "not_established"
    )
    backend_status: Literal["recomputed", "not_established"] = (
        "recomputed"
        if backend_observation is not None
        and backend_observation.observation_provenance == "recomputed"
        else "not_established"
    )
    module_status = loaded_module_observation.census_predicate
    file_bytes_status = loaded_module_observation.file_backed_bytes_predicate
    identity_status: Literal["recomputed", "not_established"] = (
        "recomputed"
        if interpreter_status == "recomputed"
        and distribution_status == "recomputed"
        and module_status == "recomputed"
        and file_bytes_status == "recomputed"
        and backend_status == "recomputed"
        else "not_established"
    )
    payload = {
        "schema_version": "N5NativeExecutionProfile@1.0",
        "authority_purpose": "candidate_execution_identity_only",
        "interpreter": interpreter,
        "platform_identity": platform_identity,
        "sys_path": sys_path,
        "sys_path_status": sys_path_status,
        "distributions": distributions,
        "distribution_census_status": distribution_status,
        "selected_environment": selected_environment,
        "declared_settings": declared_settings,
        "loaded_module_observation": loaded_module_observation,
        "backend_observation": backend_observation,
        "interpreter_platform_predicate": interpreter_status,
        "distribution_predicate": distribution_status,
        "loaded_module_predicate": module_status,
        "file_backed_module_bytes_predicate": file_bytes_status,
        "backend_predicate": backend_status,
        "first_party_source_image_predicate": "delegated_to_n5_production_image",
        "source_code_association_predicate": "not_established",
        "profile_identity_predicate": identity_status,
        "institutional_profile_admission": "not_established",
        "reason_codes": _profile_reasons(
            sys_path_status=sys_path_status,
            distributions=distributions,
            distribution_status=distribution_status,
            module_status=module_status,
            backend_status=backend_status,
        ),
    }
    return _assemble_profile(payload)


def _assemble_profile(payload: dict[str, object]) -> N5NativeExecutionProfile:
    full_content_hash = _profile_hash(payload)
    numerical_hash = _numerical_profile_content_hash_from_payload(payload)
    return N5NativeExecutionProfile.model_validate(
        {
            **payload,
            "numerical_profile_content_hash": numerical_hash,
            "content_hash": full_content_hash,
        },
        strict=True,
    )


def _numerical_profile_content_hash(profile: N5NativeExecutionProfile) -> str:
    return _numerical_profile_content_hash_from_payload(
        profile.model_dump(
            mode="json",
            exclude={"content_hash", "numerical_profile_content_hash"},
        )
    )


def _numerical_profile_content_hash_from_payload(payload: object) -> str:
    if not isinstance(payload, dict):
        raise TypeError("n5_profile_payload_invalid")
    module_observation = payload.get("loaded_module_observation")
    if isinstance(module_observation, N5LoadedModuleObservation):
        module_rows = module_observation.model_dump(mode="json")
    elif isinstance(module_observation, dict):
        module_rows = module_observation
    else:
        raise TypeError("n5_loaded_module_observation_invalid")
    image_rows = module_rows.get("file_images")
    if not isinstance(image_rows, (list, tuple)):
        raise TypeError("n5_loaded_module_file_images_invalid")
    provider_images = tuple(
        {
            key: row[key]
            for key in (
                "relative_identity",
                "file_kind",
                "coverage",
                "profile_scope",
                "byte_length",
                "content_hash",
                "row_status",
                "reason_codes",
            )
        }
        for row in image_rows
        if isinstance(row, dict) and row.get("profile_scope") != "entrypoint"
    )
    identity_payload = {
        key: payload[key]
        for key in (
            "schema_version",
            "authority_purpose",
            "interpreter",
            "platform_identity",
            "sys_path",
            "sys_path_status",
            "distributions",
            "distribution_census_status",
            "selected_environment",
            "declared_settings",
            "backend_observation",
            "interpreter_platform_predicate",
            "distribution_predicate",
            "file_backed_module_bytes_predicate",
            "backend_predicate",
            "first_party_source_image_predicate",
            "source_code_association_predicate",
            "profile_identity_predicate",
            "institutional_profile_admission",
            "reason_codes",
        )
    }
    identity_payload["provider_file_images"] = tuple(
        sorted(provider_images, key=lambda row: row["relative_identity"])
    )
    canonical = to_canonical_bytes(
        identity_payload,
        CanonSpec(forbid_floats=False, exclude_none=False),
    )
    return content_hash(canonical, prefix=True)


def reconcile_recorded_n5_profile_content(
    recorded: N5NativeExecutionProfile,
    current: N5NativeExecutionProfile,
) -> N5ProfileContentComparison:
    """Compare recorded numerical profile content with a fresh observation.

    The comparison binds every provider image captured by the recorded
    operation, while allowing the current observer to have additional ambient
    file-backed modules. It reads no paths and does not infer missing provider
    images from the filesystem.

    Args:
        recorded: Profile captured for the completed operation.
        current: Fresh profile captured at the current-use boundary.

    Returns:
        A strict result separating changed declared content from missing or
        otherwise unestablished evidence.
    """
    if (
        type(recorded) is not N5NativeExecutionProfile
        or type(current) is not N5NativeExecutionProfile
    ):
        raise TypeError("n5_profile_comparison_type_invalid")
    reasons: set[str] = set()
    matched: list[str] = []
    missing: list[str] = []
    changed: list[str] = []
    if (
        recorded.profile_identity_predicate != "recomputed"
        or current.profile_identity_predicate != "recomputed"
    ):
        reasons.add("profile_identity_not_established")
    recorded_base = _profile_base_comparison_payload(recorded)
    current_base = _profile_base_comparison_payload(current)
    if recorded_base != current_base:
        reasons.add("profile_content_changed")
    recorded_images = _provider_image_index(recorded)
    current_images = _provider_image_index(current)
    if recorded_images is None or current_images is None:
        reasons.add("provider_image_index_not_established")
    else:
        for identity, row in sorted(recorded_images.items()):
            current_row = current_images.get(identity)
            if current_row is None:
                missing.append(identity)
            elif _provider_image_identity(row) != _provider_image_identity(current_row):
                changed.append(identity)
            else:
                matched.append(identity)
    status: Literal["recomputed", "changed", "not_established"]
    if (
        reasons & {"profile_identity_not_established", "provider_image_index_not_established"}
        or missing
    ):
        status = "not_established"
    elif changed or "profile_content_changed" in reasons:
        status = "changed"
    else:
        status = "recomputed"
    return N5ProfileContentComparison(
        status=status,
        recorded_numerical_profile_content_hash=recorded.numerical_profile_content_hash,
        current_numerical_profile_content_hash=current.numerical_profile_content_hash,
        matched_provider_identities=tuple(matched),
        missing_provider_identities=tuple(missing),
        changed_provider_identities=tuple(changed),
        reason_codes=tuple(sorted(reasons)),
    )


def reconcile_recorded_n5_profile_current_bytes(
    recorded: N5NativeExecutionProfile,
    current: N5NativeExecutionProfile,
    *,
    recorded_source_image: N5ProductionImage,
    current_source_image: N5ProductionImage,
) -> N5ProfileContentComparison:
    """Compare recorded provider bytes with current admitted roots without imports.

    This is a current-byte check, not a loaded-code or execution claim. It
    accepts a recorded provider file that is not loaded in the current process
    only when its bytes can be re-observed under the current, matching
    ``sys.path``. First-party source rows are covered by equal complete source
    images; interpreter rows are checked only against the fresh interpreter
    row. The loaded-module census remains an independently recorded residual.

    Args:
        recorded: Validated profile captured after the earlier execution.
        current: Fresh native profile for the current-use process.
        recorded_source_image: Complete source image sealed with the earlier
            execution witness.
        current_source_image: Complete current source image from the native
            image owner.

    Returns:
        A typed comparison. Missing, changed, unsafe, unsupported, or
        over-budget file evidence fails closed.
    """
    from polisyos.runtime.quality.n5_execution_basis import N5ProductionImage

    if (
        type(recorded) is not N5NativeExecutionProfile
        or type(current) is not N5NativeExecutionProfile
        or type(recorded_source_image) is not N5ProductionImage
        or type(current_source_image) is not N5ProductionImage
    ):
        raise TypeError("n5_profile_current_bytes_input_type_invalid")
    try:
        recorded = N5NativeExecutionProfile.model_validate_json(recorded.model_dump_json())
        current = N5NativeExecutionProfile.model_validate_json(current.model_dump_json())
        recorded_source_image = N5ProductionImage.model_validate_json(
            recorded_source_image.model_dump_json()
        )
        current_source_image = N5ProductionImage.model_validate_json(
            current_source_image.model_dump_json()
        )
    except (TypeError, ValueError):
        raise ValueError("n5_profile_current_bytes_input_invalid") from None

    reasons: set[str] = set()
    matched: list[str] = []
    missing: list[str] = []
    changed: list[str] = []
    if (
        recorded.profile_identity_predicate != "recomputed"
        or current.profile_identity_predicate != "recomputed"
    ):
        reasons.add("profile_identity_not_established")
    if _profile_base_comparison_payload(recorded) != _profile_base_comparison_payload(current):
        reasons.add("profile_content_changed")
    if (
        recorded_source_image.provenance != "recomputed"
        or current_source_image.provenance != "recomputed"
    ):
        reasons.add("source_image_not_established")
    elif recorded_source_image.content_hash != current_source_image.content_hash:
        reasons.add("profile_content_changed")

    # Do not resolve or open any recorded file until all profile bases and the
    # separately owned complete source image match.
    if reasons:
        status: Literal["recomputed", "changed", "not_established"] = (
            "changed"
            if "profile_content_changed" in reasons
            and "profile_identity_not_established" not in reasons
            and "source_image_not_established" not in reasons
            else "not_established"
        )
        return N5ProfileContentComparison(
            status=status,
            recorded_numerical_profile_content_hash=recorded.numerical_profile_content_hash,
            current_numerical_profile_content_hash=current.numerical_profile_content_hash,
            reason_codes=tuple(sorted(reasons)),
        )

    recorded_images = _current_bytes_image_index(recorded)
    current_images = _current_bytes_image_index(current)
    if recorded_images is None or current_images is None:
        return N5ProfileContentComparison(
            status="not_established",
            recorded_numerical_profile_content_hash=recorded.numerical_profile_content_hash,
            current_numerical_profile_content_hash=current.numerical_profile_content_hash,
            reason_codes=("provider_image_index_not_established",),
        )

    recorded_sources = {
        source.relative_path: source.content_hash for source in recorded_source_image.python_sources
    }
    current_sources = {
        source.relative_path: source.content_hash for source in current_source_image.python_sources
    }
    if len(recorded_images) > _MAX_MODULE_FILES:
        return N5ProfileContentComparison(
            status="not_established",
            recorded_numerical_profile_content_hash=recorded.numerical_profile_content_hash,
            current_numerical_profile_content_hash=current.numerical_profile_content_hash,
            reason_codes=("provider_image_denominator_over_limit",),
        )

    remaining_bytes = _CURRENT_BYTES_READ_LIMIT
    for identity, row in sorted(recorded_images.items()):
        if row.profile_scope == "entrypoint":
            continue
        if row.profile_scope == "interpreter":
            current_row = current_images.get(identity)
            if current_row is None:
                missing.append(identity)
            elif _provider_bytes_identity(row) != _provider_bytes_identity(current_row):
                changed.append(identity)
            else:
                matched.append(identity)
            continue

        if row.coverage == "delegated_to_n5_production_image":
            if row.file_kind != "python_source" or not identity.startswith("first_party/polisyos/"):
                missing.append(identity)
                reasons.add("provider_file_identity_not_established")
                continue
            relative_source = identity.removeprefix("first_party/polisyos/")
            source_identity = f"src/polisyos/{relative_source}"
            recorded_hash = recorded_sources.get(source_identity)
            current_hash = current_sources.get(source_identity)
            if recorded_hash is None or current_hash is None:
                missing.append(identity)
                reasons.add("provider_file_identity_not_established")
            elif current_hash != recorded_hash:
                changed.append(identity)
            else:
                matched.append(identity)
            continue

        if row.coverage != "streamed_file_bytes" or row.file_kind not in {
            "python_source",
            "python_bytecode",
            "native_library",
        }:
            missing.append(identity)
            reasons.add("provider_file_identity_not_established")
            continue
        current_row = current_images.get(identity)
        if current_row is not None:
            if _provider_bytes_identity(row) != _provider_bytes_identity(current_row):
                changed.append(identity)
            else:
                matched.append(identity)
            continue

        path = _admitted_current_provider_path(identity, current.sys_path, row.file_kind)
        if path is None:
            missing.append(identity)
            reasons.add("provider_file_bytes_not_established")
            continue
        result = _stream_file_image(path, remaining_bytes=remaining_bytes)
        if result is None:
            missing.append(identity)
            reasons.add("provider_file_bytes_not_established")
            continue
        byte_length, digest = result
        remaining_bytes -= byte_length
        if byte_length != row.byte_length or digest != row.content_hash:
            changed.append(identity)
        else:
            matched.append(identity)

    if changed:
        reasons.add("provider_file_bytes_changed")
    if missing and not reasons:
        reasons.add("provider_file_bytes_not_established")
    if missing:
        status = "not_established"
    elif changed:
        status = "changed"
    else:
        status = "recomputed"
    return N5ProfileContentComparison(
        status=status,
        recorded_numerical_profile_content_hash=recorded.numerical_profile_content_hash,
        current_numerical_profile_content_hash=current.numerical_profile_content_hash,
        matched_provider_identities=tuple(matched),
        missing_provider_identities=tuple(missing),
        changed_provider_identities=tuple(changed),
        reason_codes=tuple(sorted(reasons)),
    )


def _current_bytes_image_index(
    profile: N5NativeExecutionProfile,
) -> dict[str, N5LoadedModuleFileImage] | None:
    rows: dict[str, N5LoadedModuleFileImage] = {}
    for row in profile.loaded_module_observation.file_images:
        if row.row_status != "recomputed" or row.relative_identity in rows:
            return None
        rows[row.relative_identity] = row
    return rows


def _admitted_current_provider_path(
    identity: str,
    sys_path: tuple[str, ...],
    file_kind: str,
) -> Path | None:
    if not _safe_relative_identity(identity):
        return None
    parts = PurePosixPath(identity).parts
    if len(parts) < 3 or parts[0] != "sys_path":
        return None
    path_index = int(parts[1])
    if path_index >= len(sys_path):
        return None
    root_value = sys_path[path_index]
    try:
        if type(root_value) is not str or not Path(root_value).is_absolute():
            return None
        root = Path(root_value).resolve(strict=True)
        relative = PurePosixPath(*parts[2:])
        if relative.is_absolute() or ".." in relative.parts:
            return None
        path = (root / Path(*relative.parts)).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            return None
        observed_kind = _module_file_kind(path)
        expected_kind: str = observed_kind or "other_file"
        if expected_kind != file_kind:
            return None
        return path
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def _profile_base_comparison_payload(profile: N5NativeExecutionProfile) -> tuple[object, ...]:
    return (
        profile.interpreter,
        profile.platform_identity,
        profile.sys_path,
        profile.distributions,
        profile.distribution_census_status,
        profile.selected_environment,
        profile.declared_settings,
        profile.backend_observation,
        profile.interpreter_platform_predicate,
        profile.distribution_predicate,
        profile.backend_predicate,
        profile.institutional_profile_admission,
    )


def _provider_image_index(
    profile: N5NativeExecutionProfile,
) -> dict[str, N5LoadedModuleFileImage] | None:
    rows: dict[str, N5LoadedModuleFileImage] = {}
    for row in profile.loaded_module_observation.file_images:
        if row.profile_scope == "entrypoint":
            continue
        if row.row_status != "recomputed" or row.relative_identity in rows:
            return None
        rows[row.relative_identity] = row
    return rows


def _provider_image_identity(row: N5LoadedModuleFileImage) -> tuple[object, ...]:
    return (
        row.file_kind,
        row.coverage,
        row.profile_scope,
        row.byte_length,
        row.content_hash,
        row.row_status,
    )


def _provider_bytes_identity(row: N5LoadedModuleFileImage) -> tuple[object, ...]:
    """Return stable bytes identity without the process-local scope label."""
    return (
        row.file_kind,
        row.coverage,
        row.byte_length,
        row.content_hash,
        row.row_status,
    )


def _profile_hash(payload: object) -> str:
    canonical = to_canonical_bytes(
        payload,
        CanonSpec(forbid_floats=False, exclude_none=False),
    )
    return content_hash(canonical, prefix=True)


__all__ = [
    "N5BackendObservation",
    "N5EnvironmentValue",
    "N5InstalledDistribution",
    "N5LoadedModuleFileImage",
    "N5LoadedModuleObservation",
    "N5NativeExecutionProfile",
    "N5ProfileContentComparison",
    "N5ProfileSetting",
    "bind_n5_backend_observation",
    "observe_n5_native_execution_profile",
    "reconcile_recorded_n5_profile_content",
    "reconcile_recorded_n5_profile_current_bytes",
]
