"""Persist and recheck the selected live judge-threshold registry snapshot.

This is a content/currentness bridge, not evidence that all required thresholds
are present, that a threshold is calibrated, or that a named approver is an
authorized issuer.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import marshal
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import CodeType, FunctionType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactStore,
    CoreArtifactOwnerProfile,
    PutOptions,
    SchemaInfo,
    require_return_selected_profile_writer,
    validate_owned_core_model_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.foundry.calibration import dp_ci as _scope_owner
from polisyos.scientist.methods.autotune import models as _registry_root_owner
from polisyos.scientist.methods.search import judge_thresholds as _threshold_owner
from polisyos.scientist.methods.search.judge_thresholds import (
    JudgeThresholdEntry,
    JudgeThresholdRegistry,
    JudgeThresholdSnapshot,
)

_KIND = "scientist.judge_threshold_basis"
_SCHEMA = "polisyos.scientist.search.JudgeThresholdBasis"
_OWNER = CoreArtifactOwnerProfile(
    kind=_KIND,
    media_type="application/json",
    schema_variants=(SchemaInfo(name=_SCHEMA, version="1.0"),),
    payload_schema_version_by_manifest=(((_SCHEMA, "1.0"), "1.0"),),
)
_REGISTRY_TYPE = JudgeThresholdRegistry
_FROZEN_REGISTRY_TYPE = _threshold_owner._FrozenJudgeThresholdRegistry
_REGISTRY_ROOT_SELECTOR = _threshold_owner.default_search_registry_root
_REGISTRY_ROOT_SELECTOR_CODE = _REGISTRY_ROOT_SELECTOR.__code__


def _owned_functions(
    namespace: object, *, module_only: bool = False
) -> dict[str, tuple[object, object]]:
    functions: dict[str, tuple[object, object]] = {}
    for name, value in vars(namespace).items():
        if isinstance(value, (classmethod, staticmethod)):
            value = value.__func__
        elif isinstance(value, property):
            value = value.fget
        if type(value) is not FunctionType:
            continue
        if module_only and value.__module__ != getattr(namespace, "__name__", None):
            continue
        functions[name] = (value, value.__code__)
    return functions


_REGISTRY_FUNCTIONS = _owned_functions(_REGISTRY_TYPE)
_FROZEN_FUNCTIONS = _owned_functions(_FROZEN_REGISTRY_TYPE)
_THRESHOLD_FUNCTIONS = _owned_functions(_threshold_owner, module_only=True)
_SCOPE_FUNCTIONS = _owned_functions(_scope_owner, module_only=True)
_THRESHOLD_CLASSES = {
    name: cls
    for name, cls in vars(_threshold_owner).items()
    if isinstance(cls, type) and cls.__module__ == _threshold_owner.__name__
}
_THRESHOLD_CLASS_FUNCTIONS = {
    name: _owned_functions(cls) for name, cls in _THRESHOLD_CLASSES.items()
}
_THRESHOLD_MODEL_OWNERS = {
    name: (cls.__pydantic_validator__, cls.__pydantic_serializer__)
    for name, cls in _THRESHOLD_CLASSES.items()
    if issubclass(cls, BaseModel)
}
_THRESHOLD_REQUIREMENTS_OWNER = _threshold_owner._THRESHOLD_REQUIREMENTS
_SCOPE_ALIASES = {
    "_normalize_scope_value": _scope_owner.normalize_ci_scope_value,
    "bucket_dp_delta": _scope_owner.bucket_dp_delta,
    "bucket_dp_epsilon": _scope_owner.bucket_dp_epsilon,
}


def _source_identity(owner: object) -> tuple[Path | None, str | None]:
    if not isinstance(owner, (type, FunctionType)):
        return None, None
    try:
        source_name = inspect.getsourcefile(owner)
        source = Path(source_name) if source_name is not None else None
        return source, hashlib.sha256(source.read_bytes()).hexdigest() if source else None
    except (OSError, TypeError):
        return None, None


_SOURCE_IDENTITIES = {
    "registry": _source_identity(_REGISTRY_TYPE),
    "scope": _source_identity(_scope_owner.normalize_ci_scope_value),
    "registry_root_selector": _source_identity(_REGISTRY_ROOT_SELECTOR),
}


def _normalized_code_constant(value: object) -> object:
    if isinstance(value, CodeType):
        return _normalized_code(value)
    if isinstance(value, tuple):
        return tuple(_normalized_code_constant(item) for item in value)
    if isinstance(value, frozenset):
        return tuple(sorted((_normalized_code_constant(item) for item in value), key=repr))
    return value


def _normalized_code(code: CodeType) -> CodeType:
    return code.replace(
        co_code=code.co_code,
        co_consts=tuple(_normalized_code_constant(item) for item in code.co_consts),
        co_filename="<selected-source>",
    )


def _code_digests(functions: dict[str, tuple[object, object]]) -> dict[str, str]:
    return {
        name: hashlib.sha256(marshal.dumps(_normalized_code(code))).hexdigest()
        for name, (_, code) in functions.items()
        if isinstance(code, CodeType)
    }


def _implementation_digest() -> str | None:
    if not all(
        path is not None and digest is not None for path, digest in _SOURCE_IDENTITIES.values()
    ):
        return None
    payload = {
        "sources": {name: digest for name, (_, digest) in _SOURCE_IDENTITIES.items()},
        "registry": _code_digests(_REGISTRY_FUNCTIONS),
        "frozen_registry": _code_digests(_FROZEN_FUNCTIONS),
        "threshold_functions": _code_digests(_THRESHOLD_FUNCTIONS),
        "scope_functions": _code_digests(_SCOPE_FUNCTIONS),
        "registry_root_selector": _code_digests(
            {"selector": (_REGISTRY_ROOT_SELECTOR, _REGISTRY_ROOT_SELECTOR_CODE)}
        ),
        "threshold_classes": {
            name: _code_digests(functions) for name, functions in _THRESHOLD_CLASS_FUNCTIONS.items()
        },
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


_REGISTRY_IMPLEMENTATION_SHA256 = _implementation_digest()


def _registry_owner_is_current(registry: JudgeThresholdRegistry | None) -> bool:
    """Check the selected in-process owner, without attesting external issuers."""
    try:
        if (
            _threshold_owner.JudgeThresholdRegistry is not _REGISTRY_TYPE
            or _threshold_owner._FrozenJudgeThresholdRegistry is not _FROZEN_REGISTRY_TYPE
            or _threshold_owner._THRESHOLD_REQUIREMENTS is not _THRESHOLD_REQUIREMENTS_OWNER
            or _threshold_owner.default_search_registry_root is not _REGISTRY_ROOT_SELECTOR
            or _registry_root_owner.default_search_registry_root is not _REGISTRY_ROOT_SELECTOR
            or _REGISTRY_ROOT_SELECTOR.__code__ is not _REGISTRY_ROOT_SELECTOR_CODE
            or _REGISTRY_IMPLEMENTATION_SHA256 is None
        ):
            return False
        if registry is not None and (
            type(registry) is not _REGISTRY_TYPE
            or set(vars(registry)) != {"_root"}
            or not isinstance(registry._root, Path)
        ):
            return False
        if any(
            path is None or hashlib.sha256(path.read_bytes()).hexdigest() != digest
            for path, digest in _SOURCE_IDENTITIES.values()
        ):
            return False
        if any(
            getattr(_threshold_owner, name, None) is not fn for name, fn in _SCOPE_ALIASES.items()
        ):
            return False
        current_classes = {
            name: cls
            for name, cls in vars(_threshold_owner).items()
            if isinstance(cls, type) and cls.__module__ == _threshold_owner.__name__
        }
        if current_classes.keys() != _THRESHOLD_CLASSES.keys() or any(
            current_classes[name] is not cls for name, cls in _THRESHOLD_CLASSES.items()
        ):
            return False
        if any(
            getattr(_THRESHOLD_CLASSES[name], "__pydantic_validator__", None) is not validator
            or getattr(_THRESHOLD_CLASSES[name], "__pydantic_serializer__", None) is not serializer
            for name, (validator, serializer) in _THRESHOLD_MODEL_OWNERS.items()
        ):
            return False
        for namespace, expected, module_only in (
            (_REGISTRY_TYPE, _REGISTRY_FUNCTIONS, False),
            (_FROZEN_REGISTRY_TYPE, _FROZEN_FUNCTIONS, False),
            (_threshold_owner, _THRESHOLD_FUNCTIONS, True),
            (_scope_owner, _SCOPE_FUNCTIONS, True),
            *(
                (cls, _THRESHOLD_CLASS_FUNCTIONS[name], False)
                for name, cls in _THRESHOLD_CLASSES.items()
            ),
        ):
            actual = _owned_functions(namespace, module_only=module_only)
            if actual.keys() != expected.keys():
                return False
            if any(
                actual[name][0] is not function or actual[name][1] is not code
                for name, (function, code) in expected.items()
            ):
                return False
        return True
    except (AttributeError, OSError, TypeError, ValueError):
        return False


def selected_judge_threshold_registry() -> JudgeThresholdRegistry:
    """Admit the selected implementation before it can select a registry root.

    Raises:
        ValueError: If the held registry or its root selector changed.
    """
    if not _registry_owner_is_current(None):
        raise ValueError("threshold_registry_owner_not_established")
    registry = _REGISTRY_TYPE()
    if not _registry_owner_is_current(registry):
        raise ValueError("threshold_registry_owner_not_established")
    return registry


class FrozenJudgeThresholdSnapshot(BaseModel):
    """Preserve the registry snapshot with immutable entries after admission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    updated_at: datetime
    entries: tuple[JudgeThresholdEntry, ...]


class JudgeThresholdBasis(BaseModel):
    """Full registry snapshot and the selected source location's identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    registry_path_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    registry_implementation_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    snapshot: FrozenJudgeThresholdSnapshot


@dataclass(frozen=True)
class JudgeThresholdBasisAdmission:
    """Recomputed currentness, separate from threshold authority."""

    status: Literal["current", "stale", "not_established", "invalid"]
    reason_code: str
    basis: JudgeThresholdBasis | None = None


def _valid_snapshot(snapshot: JudgeThresholdSnapshot | FrozenJudgeThresholdSnapshot) -> bool:
    return (
        snapshot.schema_version == "1.0"
        and bool(snapshot.entries)
        and all(math.isfinite(entry.threshold_value) for entry in snapshot.entries)
    )


def _read_live_registry(registry: JudgeThresholdRegistry) -> JudgeThresholdBasis:
    if not _registry_owner_is_current(registry):
        raise ValueError("threshold_registry_owner_not_established")
    path = registry._snapshot_path()
    if not path.is_file():
        raise ValueError("threshold_registry_not_established")
    selected_path = path.resolve(strict=True)
    snapshot = registry.snapshot()
    if (
        not _registry_owner_is_current(registry)
        or not path.is_file()
        or path.resolve(strict=True) != selected_path
    ):
        raise ValueError("threshold_registry_changed")
    if not _valid_snapshot(snapshot):
        raise ValueError("threshold_registry_invalid")
    if _REGISTRY_IMPLEMENTATION_SHA256 is None:
        raise ValueError("threshold_registry_owner_not_established")
    return JudgeThresholdBasis(
        registry_path_sha256="sha256:" + hashlib.sha256(str(selected_path).encode()).hexdigest(),
        registry_implementation_sha256="sha256:" + _REGISTRY_IMPLEMENTATION_SHA256,
        snapshot=FrozenJudgeThresholdSnapshot.model_validate(snapshot.model_dump(mode="python")),
    )


def capture_judge_threshold_basis(
    store: ArtifactStore,
    registry: JudgeThresholdRegistry,
) -> tuple[JudgeThresholdRegistry, ArtifactRef]:
    """Freeze, persist and recheck one real, finite live registry snapshot.

    Raises:
        ValueError: If the registry source is missing, invalid, or changes during capture.
    """
    before = _read_live_registry(registry)
    frozen = registry.frozen_view()
    if type(frozen) is not _FROZEN_REGISTRY_TYPE or not _registry_owner_is_current(registry):
        raise ValueError("threshold_registry_owner_not_established")
    captured = frozen.snapshot()
    if not _valid_snapshot(captured) or captured.model_dump(
        mode="json"
    ) != before.snapshot.model_dump(mode="json"):
        raise ValueError("threshold_registry_changed")
    if _read_live_registry(registry) != before:
        raise ValueError("threshold_registry_changed")
    require_return_selected_profile_writer(store, "put_json")
    ref = store.put_json(
        before,
        PutOptions(
            kind=_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_SCHEMA, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    if ref.manifest_profile_sha256 is None:
        raise ValueError("threshold_basis_profile_not_established")
    if load_judge_threshold_basis(store, ref) != before or _read_live_registry(registry) != before:
        raise ValueError("threshold_registry_changed")
    return frozen, ref


def load_judge_threshold_basis(store: ArtifactStore, ref: ArtifactRef) -> JudgeThresholdBasis:
    """Read this owner's selected threshold basis without granting authority."""
    if ref.manifest_profile_sha256 is None:
        raise ValueError("threshold_basis_profile_not_established")
    basis = validate_owned_core_model_json_artifact(
        JudgeThresholdBasis, store, ref, expected_owner=_OWNER
    ).value
    if not _valid_snapshot(basis.snapshot):
        raise ValueError("threshold_registry_invalid")
    return basis


def resolve_judge_threshold_basis(
    store: ArtifactStore,
    ref: ArtifactRef,
    registry: JudgeThresholdRegistry,
) -> JudgeThresholdBasisAdmission:
    """Reconcile an exact selected basis with the currently selected live registry."""
    if ref.manifest_profile_sha256 is None:
        return JudgeThresholdBasisAdmission("not_established", "threshold_basis_profile_missing")
    try:
        basis = load_judge_threshold_basis(store, ref)
    except (OSError, RuntimeError, TypeError, ValueError):
        return JudgeThresholdBasisAdmission("invalid", "threshold_basis_owner_invalid")
    try:
        current = _read_live_registry(registry)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        if str(exc) == "threshold_registry_changed":
            return JudgeThresholdBasisAdmission("stale", "threshold_registry_changed", basis)
        return JudgeThresholdBasisAdmission(
            "not_established", "threshold_registry_unavailable", basis
        )
    if current.registry_path_sha256 != basis.registry_path_sha256:
        return JudgeThresholdBasisAdmission("stale", "threshold_registry_source_changed", basis)
    if current.registry_implementation_sha256 != basis.registry_implementation_sha256:
        return JudgeThresholdBasisAdmission(
            "stale", "threshold_registry_implementation_changed", basis
        )
    if current.snapshot != basis.snapshot:
        return JudgeThresholdBasisAdmission("stale", "threshold_registry_snapshot_changed", basis)
    return JudgeThresholdBasisAdmission("current", "threshold_basis_current", basis)


__all__ = [
    "FrozenJudgeThresholdSnapshot",
    "JudgeThresholdBasis",
    "JudgeThresholdBasisAdmission",
    "capture_judge_threshold_basis",
    "load_judge_threshold_basis",
    "resolve_judge_threshold_basis",
    "selected_judge_threshold_registry",
]
