"""Owner-controlled local runtime material for Legal embedding generations.

This is a narrow Legal extension of the existing generation writer and reader.
It does not select a production source, confer legal authority, or accept a
caller-provided encoder as proof of executable identity.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import marshal
import platform
import re
import site
import sys
import sysconfig
from contextlib import contextmanager
from importlib import metadata
from pathlib import Path, PurePosixPath
from threading import RLock
from typing import TYPE_CHECKING, cast

from polisyos.data_forge.kernel.embeddings import derive_encoder_identity

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from sentence_transformers import SentenceTransformer

    from polisyos.data_forge.kernel.io.generation_basis import GenerationIdentity

LEGAL_RUNTIME_MATERIAL_RULE_VERSION = "legal.runtime_material.v2"
LEGAL_CONTROLLED_MODEL_ID = "intfloat/multilingual-e5-large"
LEGAL_CONTROLLED_MODEL_REVISION = "3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3"
LEGAL_CONTROLLED_MODEL_REFERENCE = f"{LEGAL_CONTROLLED_MODEL_ID}@{LEGAL_CONTROLLED_MODEL_REVISION}"
LEGAL_CONTROLLED_ST_VERSION = "2.7.0"
LEGAL_CONTROLLED_MANIFEST_SHA256 = (
    "191a71ec41bc1a69665fffccb5fa7f1c30b3f94ccd60f71cc3ed1f074ecb98ca"
)

_SOURCE_FILES = (
    "polisyos/data_forge/domains/legal/runtime_material.py",
    "polisyos/data_forge/domains/legal/batch/embedder.py",
    "polisyos/data_forge/domains/legal/embedding_projection.py",
    "polisyos/data_forge/kernel/embeddings.py",
    "polisyos/data_forge/kernel/io/generation_basis.py",
    "polisyos/data_forge/read_api/legal.py",
    "polisyos/lex/knowledge/store.py",
    "polisyos/lex/knowledge/search.py",
)
_RUNTIME_ROOT_DISTRIBUTIONS = (
    "sentence-transformers",
    "sentencepiece",
    "hnswlib",
    "packaging",
)
_RUNTIME_PROFILE_MODULES = (
    "sentence_transformers",
    "sentencepiece",
    "hnswlib",
    "torch",
    "transformers",
    "tokenizers",
    "huggingface_hub",
    "hashlib",
    "json",
    "marshal",
    "platform",
    "re",
    "site",
    "sysconfig",
    "importlib.metadata",
    "packaging",
    "packaging.markers",
    "packaging.requirements",
    "_hashlib",
)
_REQUIRED_RUNTIME_PROFILE_MODULES = (
    "sentence_transformers",
    "torch",
    "huggingface_hub",
)
_PRODUCER_SETTINGS: dict[str, object] = {
    "batch_size": 1,
    "show_progress_bar": False,
    "normalize_embeddings": True,
    "output_value": "sentence_embedding",
    "convert_to_numpy": True,
    "convert_to_tensor": False,
    "device": "cpu",
}
_QUERY_SETTINGS: dict[str, object] = {
    "batch_size": 1,
    "show_progress_bar": False,
    "normalize_embeddings": True,
    "output_value": "sentence_embedding",
    "convert_to_numpy": True,
    "convert_to_tensor": False,
    "device": "cpu",
}
_PRODUCER_CHUNK_SIZE = 8
_HANDLE_SEAL = object()


class LegalRuntimeMaterialError(ValueError):
    """Typed refusal from the source-owned Legal runtime-material owner."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_digest(value: object) -> str:
    """Hash a canonical JSON-compatible value."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> tuple[str, int]:
    """Recompute one regular file's digest without following a new locator set."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _safe_local_file(path: Path, *, error_code: str = "query_encoder_assets_unavailable") -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise LegalRuntimeMaterialError(error_code) from exc
    if not resolved.is_file():
        raise LegalRuntimeMaterialError(error_code)
    return resolved


def _model_file_inventory(
    *,
    snapshot: Path,
    cache_root: Path,
    manifest_path: Path,
) -> tuple[str, tuple[dict[str, object], ...]]:
    """Resolve only pinned manifest members and rehash their actual bytes.

    Hugging Face snapshot symlinks are accepted only when their resolved regular
    files remain in this exact revision or its model-specific blob directory.
    Inode and symlink-target strings are locators, not material identity.
    """
    try:
        manifest_bytes = manifest_path.read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != LEGAL_CONTROLLED_MANIFEST_SHA256:
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
        manifest = json.loads(manifest_bytes)
    except LegalRuntimeMaterialError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established") from exc

    if (
        not isinstance(manifest, dict)
        or manifest.get("revision") != LEGAL_CONTROLLED_MODEL_REVISION
        or manifest.get("named_file_count") != 9
        or not isinstance(manifest.get("files"), list)
        or len(manifest["files"]) != 9
    ):
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")

    try:
        resolved_cache_root = cache_root.resolve(strict=True)
        resolved_snapshot = snapshot.resolve(strict=True)
        model_cache_directory = f"models--{LEGAL_CONTROLLED_MODEL_ID.replace('/', '--')}"
        resolved_model_root = (resolved_cache_root / model_cache_directory).resolve(strict=True)
        resolved_snapshots_root = (resolved_model_root / "snapshots").resolve(strict=True)
        resolved_blobs_root = (resolved_model_root / "blobs").resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established") from exc
    if (
        not resolved_cache_root.is_dir()
        or not resolved_model_root.is_dir()
        or not resolved_model_root.is_relative_to(resolved_cache_root)
        or not resolved_snapshot.is_dir()
        or not resolved_snapshots_root.is_dir()
        or not resolved_snapshots_root.is_relative_to(resolved_model_root)
        or not resolved_blobs_root.is_relative_to(resolved_model_root)
        or (resolved_blobs_root.exists() and not resolved_blobs_root.is_dir())
        or resolved_snapshot.name != LEGAL_CONTROLLED_MODEL_REVISION
        or resolved_snapshot.parent != resolved_snapshots_root
    ):
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")

    members: list[dict[str, object]] = []
    seen: set[str] = set()
    logical_bytes = 0
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
        name = entry.get("name")
        if not isinstance(name, str):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
        expected_digest = entry.get("sha256")
        expected_size = entry.get("size_bytes")
        if (
            not isinstance(expected_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
            or not isinstance(expected_size, int)
            or isinstance(expected_size, bool)
            or expected_size < 0
        ):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
        member = PurePosixPath(name)
        if (
            member.is_absolute()
            or not member.parts
            or any(part in ("", ".", "..") for part in member.parts)
            or name in seen
        ):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
        seen.add(name)
        resolved_member = _safe_local_file(resolved_snapshot.joinpath(*member.parts))
        if not (
            resolved_member.is_relative_to(resolved_snapshot)
            or resolved_member.is_relative_to(resolved_blobs_root)
        ):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
        actual_digest, actual_size = _sha256_file(resolved_member)
        if actual_digest != expected_digest or actual_size != expected_size:
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
        logical_bytes += actual_size
        members.append(
            {
                "name": name,
                "sha256": actual_digest,
                "size_bytes": actual_size,
            }
        )
    if len(seen) != 9 or logical_bytes != manifest.get("logical_bytes"):
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
    ordered = tuple(sorted(members, key=lambda item: str(item["name"])))
    return _canonical_digest(
        {
            "manifest_sha256": LEGAL_CONTROLLED_MANIFEST_SHA256,
            "model_id": LEGAL_CONTROLLED_MODEL_ID,
            "revision": LEGAL_CONTROLLED_MODEL_REVISION,
            "members": ordered,
        }
    ), ordered


def _runtime_path_record(value: str) -> dict[str, str]:
    """Bind the spelling and resolved target of one active import/site path."""
    if not isinstance(value, str):
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
    try:
        resolved = Path(value or ".").resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established") from exc
    return {"invocation_path": value, "resolved_path": str(resolved)}


def _loaded_runtime_module_profile() -> dict[str, dict[str, object]]:
    """Bind loaded runtime module origins to their current regular-file bytes."""
    profile: dict[str, dict[str, object]] = {}
    for name in _RUNTIME_PROFILE_MODULES:
        module = sys.modules.get(name)
        if module is None:
            profile[name] = {"state": "not_loaded"}
            continue
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None)
        module_file = getattr(module, "__file__", None)
        if not isinstance(module_file, str):
            profile[name] = {
                "state": "loaded_without_file",
                "origin": origin if isinstance(origin, str) else None,
            }
            continue
        resolved_file = _safe_local_file(
            Path(module_file),
            error_code="query_encoder_runtime_material_not_established",
        )
        digest, size = _sha256_file(resolved_file)
        profile[name] = {
            "state": "loaded_file",
            "origin": origin if isinstance(origin, str) else None,
            "invocation_path": module_file,
            "resolved_path": str(resolved_file),
            "sha256": digest,
            "size_bytes": size,
        }
    return profile


def _load_runtime_profile_modules() -> None:
    """Load every owner-profile module before recording its initial state."""
    for name in _RUNTIME_PROFILE_MODULES:
        try:
            importlib.import_module(name)
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise LegalRuntimeMaterialError(
                "query_encoder_runtime_material_not_established"
            ) from exc


def _python_execution_profile(
    executable_invocation_path: str | None = None,
    *,
    require_loaded_runtime_modules: bool = True,
) -> dict[str, object]:
    """Capture the effective interpreter invocation, import paths, and modules.

    The raw executable path is preserved alongside its resolved binary. Venv
    launchers may share one binary while selecting distinct prefixes and site
    packages, so hashing the resolved executable alone is not an environment
    identity.
    """
    invocation_path = (
        sys.executable if executable_invocation_path is None else executable_invocation_path
    )
    if not isinstance(invocation_path, str) or not invocation_path:
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
    executable = _safe_local_file(
        Path(invocation_path),
        error_code="query_encoder_runtime_material_not_established",
    )
    executable_digest, executable_size = _sha256_file(executable)
    raw_base_executable = getattr(sys, "_base_executable", None)
    if raw_base_executable is None:
        base_executable_profile: dict[str, object] | None = None
    elif isinstance(raw_base_executable, str) and raw_base_executable:
        base_executable = _safe_local_file(
            Path(raw_base_executable),
            error_code="query_encoder_runtime_material_not_established",
        )
        base_digest, base_size = _sha256_file(base_executable)
        base_executable_profile = {
            "invocation_path": raw_base_executable,
            "resolved_path": str(base_executable),
            "sha256": base_digest,
            "size_bytes": base_size,
        }
    else:
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
    try:
        raw_site_packages = site.getsitepackages()
        raw_user_site = site.getusersitepackages()
        configured_paths = sysconfig.get_paths()
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established") from exc
    if not isinstance(raw_user_site, str):
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
    user_site_packages = [raw_user_site]
    if not isinstance(raw_site_packages, (list, tuple)) or not all(
        isinstance(path, str) for path in raw_site_packages
    ):
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
    if not isinstance(configured_paths, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in configured_paths.items()
    ):
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
    if not all(isinstance(path, str) for path in sys.path):
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")

    loaded_modules = _loaded_runtime_module_profile()
    if require_loaded_runtime_modules and any(
        loaded_modules[name].get("state") != "loaded_file"
        for name in _REQUIRED_RUNTIME_PROFILE_MODULES
    ):
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
    return {
        "implementation": platform.python_implementation(),
        "version": sys.version,
        "machine": platform.machine(),
        "system": platform.system(),
        "executable_invocation_path": invocation_path,
        "executable_resolved_path": str(executable),
        "executable_sha256": executable_digest,
        "executable_size_bytes": executable_size,
        "base_executable": base_executable_profile,
        "invocation_flags": {
            name: getattr(sys.flags, name, None)
            for name in (
                "no_site",
                "no_user_site",
                "ignore_environment",
                "isolated",
                "safe_path",
                "optimize",
                "utf8_mode",
            )
        },
        "dont_write_bytecode": sys.dont_write_bytecode,
        "prefixes": {
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
            "exec_prefix": sys.exec_prefix,
            "base_exec_prefix": sys.base_exec_prefix,
        },
        "sys_path": [_runtime_path_record(path) for path in sys.path],
        "site_packages": {
            "global": [_runtime_path_record(path) for path in raw_site_packages],
            "user": [_runtime_path_record(path) for path in user_site_packages],
            "user_site_enabled": site.ENABLE_USER_SITE,
        },
        "sysconfig_paths": {
            key: _runtime_path_record(value) for key, value in sorted(configured_paths.items())
        },
        "loaded_modules": loaded_modules,
    }


def _installed_runtime_digest() -> str:
    """Recompute the installed Python distribution closure from actual files."""
    try:
        from packaging.markers import default_environment
        from packaging.requirements import Requirement
    except ImportError as exc:
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established") from exc

    environment: dict[str, str] = {}
    for key, value in default_environment().items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
        environment[key] = value
    environment["extra"] = ""
    pending: list[str] = list(_RUNTIME_ROOT_DISTRIBUTIONS)
    resolved: dict[str, dict[str, object]] = {}
    while pending:
        requested = pending.pop()
        normalized = re.sub(r"[-_.]+", "-", requested).lower()
        if normalized in resolved:
            continue
        try:
            distribution = metadata.distribution(requested)
            distribution_name = distribution.metadata.get("Name")
            version = distribution.version
            files = distribution.files
        except (metadata.PackageNotFoundError, OSError, ValueError) as exc:
            raise LegalRuntimeMaterialError(
                "query_encoder_runtime_material_not_established"
            ) from exc
        if not isinstance(distribution_name, str) or files is None:
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")

        file_records: list[dict[str, object]] = []
        for item in sorted(files, key=lambda path: str(path)):
            resolved_file = _safe_local_file(
                Path(str(distribution.locate_file(item))),
                error_code="query_encoder_runtime_material_not_established",
            )
            file_digest, file_size = _sha256_file(resolved_file)
            file_records.append(
                {
                    "distribution_path": str(item).replace("\\", "/"),
                    "sha256": file_digest,
                    "size_bytes": file_size,
                }
            )
        resolved[normalized] = {
            "name": distribution_name,
            "version": version,
            "files": file_records,
        }
        try:
            for requirement_text in distribution.requires or ():
                requirement = Requirement(requirement_text)
                if requirement.marker is not None and not requirement.marker.evaluate(environment):
                    continue
                pending.append(requirement.name)
        except (TypeError, ValueError) as exc:
            raise LegalRuntimeMaterialError(
                "query_encoder_runtime_material_not_established"
            ) from exc

    return _canonical_digest(
        {
            "distributions": resolved,
            "python_execution_profile": _python_execution_profile(),
        }
    )


def _source_closure_digest() -> str:
    """Rehash the bounded Legal producer, loader, and shared reader sources."""
    package_root = Path(__file__).resolve().parents[4]
    source_records: list[dict[str, str]] = []
    for relative in _SOURCE_FILES:
        source_path = _safe_local_file(
            package_root / relative,
            error_code="query_encoder_runtime_material_not_established",
        )
        source_records.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            }
        )
    return _canonical_digest(source_records)


def _encode_method_fingerprint(method: object) -> str:
    """Fingerprint the actual bound SentenceTransformer encode implementation."""
    function = getattr(method, "__func__", None)
    code = getattr(function, "__code__", None)
    if function is None or code is None:
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
    try:
        defaults = {
            "defaults": getattr(function, "__defaults__", None),
            "kwdefaults": getattr(function, "__kwdefaults__", None),
        }
        return _canonical_digest(
            {
                "code_sha256": hashlib.sha256(marshal.dumps(code)).hexdigest(),
                "function_module": getattr(function, "__module__", ""),
                "function_name": getattr(function, "__qualname__", ""),
                "defaults": defaults,
            }
        )
    except (TypeError, ValueError) as exc:
        raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established") from exc


def _settings() -> dict[str, object]:
    return {
        "model_reference": LEGAL_CONTROLLED_MODEL_REFERENCE,
        "model_device": "cpu",
        "model_kwargs": {},
        "producer_batch_size": 1,
        "producer_chunk_size": _PRODUCER_CHUNK_SIZE,
        "producer_encode": dict(_PRODUCER_SETTINGS),
        "query_encode": dict(_QUERY_SETTINGS),
    }


def _binding_digest(
    *,
    model_files_digest: str,
    asset_identity: GenerationIdentity,
    runtime_digest: str,
    source_digest: str,
    encode_fingerprint: str,
) -> str:
    return _canonical_digest(
        {
            "rule": LEGAL_RUNTIME_MATERIAL_RULE_VERSION,
            "model_files_digest": model_files_digest,
            "loaded_asset_identity": asset_identity.content_identity,
            "installed_runtime_digest": runtime_digest,
            "source_closure_digest": source_digest,
            "encode_method_fingerprint": encode_fingerprint,
            "effective_settings": _settings(),
        }
    )


class LegalRuntimeMaterialOwner:
    """Resolve the exact supported Legal model locally and issue checked handles.

    Only the cache and named manifest locators are supplied by the application.
    Model ID, revision, manifest bytes, device, package version, and encode
    settings are source-owned constants. This is a controlled reproducibility
    profile, not a production-source or authority selection. Its bounded
    candidate claim assumes a trusted process: no concurrent external mutation
    of model/runtime state during leases and no mutation of callable globals or
    closure state while the profile is admitted. Untrusted in-process plugins
    are outside scope. The owner lock protects resolution, not model aliases.
    """

    def __init__(self, *, cache_root: Path, manifest_path: Path) -> None:
        if not isinstance(cache_root, Path) or not isinstance(manifest_path, Path):
            raise TypeError("legal_runtime_material_locators_invalid")
        self._cache_root = cache_root.expanduser().resolve()
        self._manifest_path = manifest_path.expanduser().resolve()
        self._lock = RLock()
        self._handles: dict[str, LegalRuntimeMaterialHandle] = {}
        self._handle: LegalRuntimeMaterialHandle | None = None

    @classmethod
    def from_profile_root(cls, profile_root: Path) -> LegalRuntimeMaterialOwner:
        """Bind the source-pinned profile's fixed cache and manifest members.

        The profile root is an operator-supplied locator, not a profile
        declaration. Model identity, manifest digest, member inventory, and
        runtime settings remain source-owned and are revalidated before model
        loading. Invalid explicit roots refuse instead of falling back to an
        unowned encoder.
        """
        if not isinstance(profile_root, Path):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
        try:
            resolved_root = profile_root.expanduser().resolve(strict=True)
            resolved_cache = (resolved_root / "hf-cache").resolve(strict=True)
            resolved_manifest = (resolved_root / "asset-file-manifest.txt").resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise LegalRuntimeMaterialError(
                "query_encoder_runtime_material_not_established"
            ) from exc

        if (
            not resolved_root.is_dir()
            or not resolved_cache.is_dir()
            or not resolved_manifest.is_file()
            or not resolved_cache.is_relative_to(resolved_root)
            or not resolved_manifest.is_relative_to(resolved_root)
        ):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")
        try:
            manifest_digest, _manifest_size = _sha256_file(resolved_manifest)
        except OSError as exc:
            raise LegalRuntimeMaterialError(
                "query_encoder_runtime_material_not_established"
            ) from exc
        if manifest_digest != LEGAL_CONTROLLED_MANIFEST_SHA256:
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_not_established")

        return cls(cache_root=resolved_cache, manifest_path=resolved_manifest)

    @property
    def embedding_model(self) -> str:
        """Return the source-pinned immutable model reference."""
        return LEGAL_CONTROLLED_MODEL_REFERENCE

    @property
    def embedding_device(self) -> str:
        """Return the source-pinned device."""
        return "cpu"

    @property
    def producer_batch_size(self) -> int:
        """Return the controlled producer encode batch size."""
        return 1

    @property
    def producer_chunk_size(self) -> int:
        """Return the controlled producer row chunk size."""
        return _PRODUCER_CHUNK_SIZE

    def resolve_encoder(self) -> LegalRuntimeMaterialHandle:
        """Load once from the exact local revision and return its source-issued handle."""
        with self._lock:
            if self._handle is not None:
                return self._handle
            try:
                from huggingface_hub import snapshot_download

                snapshot = Path(
                    snapshot_download(
                        repo_id=LEGAL_CONTROLLED_MODEL_ID,
                        revision=LEGAL_CONTROLLED_MODEL_REVISION,
                        cache_dir=str(self._cache_root),
                        local_files_only=True,
                    )
                ).resolve(strict=True)
                model_files_digest, _model_members = _model_file_inventory(
                    snapshot=snapshot,
                    cache_root=self._cache_root,
                    manifest_path=self._manifest_path,
                )
                if metadata.version("sentence-transformers") != LEGAL_CONTROLLED_ST_VERSION:
                    raise LegalRuntimeMaterialError(
                        "query_encoder_runtime_material_not_established"
                    )
                _load_runtime_profile_modules()
                source_digest_before_load = _source_closure_digest()
                from sentence_transformers import SentenceTransformer

                model = SentenceTransformer(str(snapshot), device="cpu")
                eval_method = getattr(model, "eval", None)
                if not callable(eval_method):
                    raise LegalRuntimeMaterialError(
                        "query_encoder_runtime_material_not_established"
                    )
                eval_method()
                model_files_digest_after_load, _loaded_model_members = _model_file_inventory(
                    snapshot=snapshot,
                    cache_root=self._cache_root,
                    manifest_path=self._manifest_path,
                )
                if model_files_digest_after_load != model_files_digest:
                    raise LegalRuntimeMaterialError(
                        "query_encoder_runtime_material_not_established"
                    )
                runtime_digest = _installed_runtime_digest()
                source_digest = _source_closure_digest()
                if source_digest != source_digest_before_load:
                    raise LegalRuntimeMaterialError(
                        "query_encoder_runtime_material_not_established"
                    )
                actual_device = str(getattr(model, "device", ""))
                dimension = model.get_sentence_embedding_dimension()
                if dimension is None:
                    raise LegalRuntimeMaterialError(
                        "query_encoder_runtime_material_not_established"
                    )
                if actual_device != "cpu" or dimension != 1024:
                    raise LegalRuntimeMaterialError(
                        "query_encoder_runtime_material_not_established"
                    )
                asset_identity = derive_encoder_identity(
                    model,
                    include_live_model_state=True,
                    require_zero_copy=True,
                )
                if "encode" in getattr(model, "__dict__", {}):
                    raise LegalRuntimeMaterialError(
                        "query_encoder_runtime_material_not_established"
                    )
                bound_encode = getattr(model, "encode", None)
                if getattr(bound_encode, "__self__", None) is not model:
                    raise LegalRuntimeMaterialError(
                        "query_encoder_runtime_material_not_established"
                    )
                encode_fingerprint = _encode_method_fingerprint(bound_encode)
                binding_digest = _binding_digest(
                    model_files_digest=model_files_digest,
                    asset_identity=asset_identity,
                    runtime_digest=runtime_digest,
                    source_digest=source_digest,
                    encode_fingerprint=encode_fingerprint,
                )
                handle = LegalRuntimeMaterialHandle(
                    owner=self,
                    model=model,
                    asset_identity=asset_identity,
                    model_files_digest=model_files_digest,
                    runtime_digest=runtime_digest,
                    source_digest=source_digest,
                    encode_fingerprint=encode_fingerprint,
                    binding_digest=binding_digest,
                    bound_encode=bound_encode,
                    _seal=_HANDLE_SEAL,
                )
            except LegalRuntimeMaterialError:
                raise
            except Exception as exc:
                raise LegalRuntimeMaterialError(
                    "query_encoder_runtime_material_not_established"
                ) from exc
            self._handles[binding_digest] = handle
            self._handle = handle
            return handle

    def _owns(self, handle: LegalRuntimeMaterialHandle) -> bool:
        return self._handles.get(handle.binding_digest) is handle


class LegalRuntimeMaterialHandle:
    """Live encoder handle guarded by pre/post checks on owner-issued leases.

    The lease lock serializes calls through this handle only. It does not prevent
    direct in-process mutation through another model reference or make pre/post
    checks atomic against concurrent mutation and restoration. Its callable
    fingerprint does not bind mutable closure cells or globals.
    """

    __slots__ = (
        "_asset_identity",
        "_binding_digest",
        "_bound_encode",
        "_encode_fingerprint",
        "_lock",
        "_model",
        "_model_files_digest",
        "_owner",
        "_runtime_digest",
        "_seal",
        "_source_digest",
    )

    def __init__(
        self,
        *,
        owner: LegalRuntimeMaterialOwner,
        model: SentenceTransformer,
        asset_identity: GenerationIdentity,
        model_files_digest: str,
        runtime_digest: str,
        source_digest: str,
        encode_fingerprint: str,
        binding_digest: str,
        bound_encode: object,
        _seal: object,
    ) -> None:
        if _seal is not _HANDLE_SEAL:
            raise TypeError("legal_runtime_material_handle_owner_required")
        self._owner = owner
        self._model = model
        self._asset_identity = asset_identity
        self._model_files_digest = model_files_digest
        self._runtime_digest = runtime_digest
        self._source_digest = source_digest
        self._encode_fingerprint = encode_fingerprint
        self._binding_digest = binding_digest
        self._bound_encode = bound_encode
        self._lock = RLock()
        self._seal = _seal

    @property
    def binding_digest(self) -> str:
        """Return the material binding included in Legal generation rules."""
        return self._binding_digest

    @property
    def projection_rule_version(self) -> str:
        """Return the Legal projection rule extended by this runtime binding."""
        from polisyos.data_forge.domains.legal.embedding_projection import (
            LEGAL_EMBEDDING_PROJECTION_RULE_VERSION,
        )

        return (
            f"{LEGAL_EMBEDDING_PROJECTION_RULE_VERSION}|"
            f"{LEGAL_RUNTIME_MATERIAL_RULE_VERSION}={self.binding_digest}"
        )

    @property
    def asset_identity(self) -> GenerationIdentity:
        """Return the owner-derived loaded model asset identity."""
        return self._asset_identity

    def __getattr__(self, name: str) -> object:
        return getattr(object.__getattribute__(self, "_model"), name)

    def encode(self, *_args: object, **_kwargs: object) -> object:
        """Prevent calls outside the producer helper or shared reader gate."""
        raise LegalRuntimeMaterialError("query_encoder_call_requires_shared_gate")

    def _assert_live(
        self, expected_binding: str, expected_assets: GenerationIdentity
    ) -> Callable[..., object]:
        if (
            self._seal is not _HANDLE_SEAL
            or not self._owner._owns(self)
            or expected_binding != self._binding_digest
            or expected_assets != self._asset_identity
        ):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_changed")
        model = self._model
        if "encode" in getattr(model, "__dict__", {}):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_changed")
        current_encode = getattr(model, "encode", None)
        if getattr(current_encode, "__self__", None) is not model or getattr(
            current_encode, "__func__", None
        ) is not getattr(self._bound_encode, "__func__", None):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_changed")
        try:
            current_device = str(model.device)
            dimension = model.get_sentence_embedding_dimension()
            if dimension is None:
                raise ValueError("legal_embedding_dimension_unavailable")
            current_dimension = int(dimension)
            current_assets = derive_encoder_identity(
                model,
                include_live_model_state=True,
                require_zero_copy=True,
            )
        except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_changed") from exc
        if (
            current_device != "cpu"
            or current_dimension != 1024
            or current_assets != self._asset_identity
        ):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_changed")
        current_runtime = _installed_runtime_digest()
        if current_runtime != self._runtime_digest:
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_changed")
        current_fingerprint = _encode_method_fingerprint(current_encode)
        current_source = _source_closure_digest()
        live_binding = _binding_digest(
            model_files_digest=self._model_files_digest,
            asset_identity=self._asset_identity,
            runtime_digest=current_runtime,
            source_digest=current_source,
            encode_fingerprint=current_fingerprint,
        )
        if live_binding != self._binding_digest:
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_changed")
        return cast("Callable[..., object]", current_encode)

    @contextmanager
    def checked_encode_lease(
        self,
        *,
        expected_binding: str,
        expected_assets: GenerationIdentity,
    ) -> Iterator[Callable[..., object]]:
        """Capture the method and hold its checked lease over one encode call.

        The handle lock serializes these leases, not external model mutation.
        Pre/post checks detect persistent changes; they are not an atomic snapshot
        against concurrent mutation and restoration, and callable closure/global
        state remains within the trusted-process assumption.
        """
        with self._lock:
            encode = self._assert_live(expected_binding, expected_assets)
            if encode is None:
                encode = getattr(self._model, "encode", None)
            if not callable(encode):
                raise LegalRuntimeMaterialError("query_encoder_runtime_material_changed")
            try:
                yield encode
            finally:
                self._assert_live(expected_binding, expected_assets)

    def encode_for_generation(
        self,
        texts: list[str],
        *,
        batch_size: int,
        show_progress_bar: bool,
        normalize_embeddings: bool,
    ) -> object:
        """Encode producer rows under the exact source-owned producer settings."""
        if (
            batch_size != self._owner.producer_batch_size
            or show_progress_bar is not False
            or normalize_embeddings is not True
        ):
            raise LegalRuntimeMaterialError("query_encoder_runtime_material_changed")
        with self.checked_encode_lease(
            expected_binding=self.binding_digest,
            expected_assets=self.asset_identity,
        ) as encode:
            return encode(texts, **dict(_PRODUCER_SETTINGS))

    def encode_for_query(
        self,
        texts: list[str],
        *,
        expected_binding: str,
        expected_assets: GenerationIdentity,
    ) -> object:
        """Encode query text using the same checked owner-issued callable."""
        with self.checked_encode_lease(
            expected_binding=expected_binding,
            expected_assets=expected_assets,
        ) as encode:
            return encode(texts, **dict(_QUERY_SETTINGS))
