"""Independent semantic oracle for AD-E02-FABRIC-REFLECTION-01.

Each product import and hint resolution runs in a child interpreter. This oracle
is source-checkout-only: it binds imported module origins and bytes to source paths
derived from this test's repository context. It does not claim installed-profile
coverage. The eight selected callable contracts, WorldQueryRequest, four bounded
mode routes, and two existing ConnectorMetadataSpec checks remain separate.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from types import FunctionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from importlib.machinery import ModuleSpec
    from types import ModuleType

import pytest


def _project_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "src" / "polisyos").is_dir() and (candidate / "tests").is_dir():
            return candidate
    raise AssertionError("oracle file is not inside a source checkout")


_SOURCE_MANIFEST_ENV = "POLISYOS_FABRIC_REFLECTION_SOURCE_MANIFEST"
_SOURCE_MODULE_NAMES = (
    "polisyos",
    "polisyos.core",
    "polisyos.core.contracts",
    "polisyos.core.contracts.runtime",
    "polisyos.core.security",
    "polisyos.fabric",
    "polisyos.fabric.connectors",
    "polisyos.fabric.connectors.base",
    "polisyos.fabric.connectors.cache",
    "polisyos.fabric.connectors.cache.invalidation",
    "polisyos.fabric.connectors.cache.store",
    "polisyos.fabric.connectors.contracts",
    "polisyos.fabric.data_plane",
    "polisyos.fabric.data_plane.modes",
    "polisyos.fabric.data_plane.orchestrator",
    "polisyos.fabric.evidence",
    "polisyos.fabric.evidence.decision_data",
    "polisyos.fabric.io",
    "polisyos.fabric.io.db",
    "polisyos.fabric.security",
    "polisyos.fabric.world",
    "polisyos.fabric.world.query",
    "polisyos.ir",
    "polisyos.ir.connectors",
)
_TARGET_SOURCE_MODULES = (
    "polisyos",
    "polisyos.fabric",
    "polisyos.fabric.connectors",
    "polisyos.fabric.connectors.cache",
    "polisyos.fabric.connectors.cache.invalidation",
    "polisyos.fabric.connectors.base",
    "polisyos.fabric.connectors.cache.store",
    "polisyos.fabric.data_plane",
    "polisyos.fabric.data_plane.modes",
    "polisyos.fabric.evidence",
    "polisyos.fabric.evidence.decision_data",
    "polisyos.fabric.world",
    "polisyos.fabric.world.query",
    "polisyos.fabric.io",
    "polisyos.fabric.io.db",
    "polisyos.core",
    "polisyos.core.contracts",
    "polisyos.core.contracts.runtime",
    "polisyos.core.security",
    "polisyos.ir",
    "polisyos.ir.connectors",
)
_SEMANTIC_SOURCE_MODULES = (
    "polisyos",
    "polisyos.fabric",
    "polisyos.fabric.connectors",
    "polisyos.fabric.connectors.cache",
    "polisyos.fabric.connectors.cache.invalidation",
    "polisyos.fabric.connectors.cache.store",
    "polisyos.fabric.connectors.base",
    "polisyos.fabric.evidence",
    "polisyos.fabric.evidence.decision_data",
    "polisyos.fabric.world",
    "polisyos.fabric.world.query",
    "polisyos.fabric.io",
    "polisyos.fabric.io.db",
    "polisyos.core",
    "polisyos.core.contracts",
    "polisyos.core.contracts.runtime",
    "polisyos.core.security",
    "polisyos.ir",
    "polisyos.ir.connectors",
)
_CONSUMER_SOURCE_MODULES = (
    "polisyos.pdc",
    "polisyos.pdc._impl",
    "polisyos.pdc._impl.world_model_record",
    "polisyos.runtime",
    "polisyos.runtime.quality",
    "polisyos.runtime.quality.world_model_record",
)
_SELECTED_PUBLIC_NAMES = {
    "polisyos.fabric": {
        "TemporalRef",
        "WorldQueryRequest",
        "query_world_table",
        "query_claims",
        "query_events",
    },
    "polisyos.fabric.connectors": {
        "InvalidationTrigger",
        "InvalidationOrchestrator",
        "SchemaChangeInvalidationTrigger",
    },
    "polisyos.fabric.data_plane": {"query_world_table"},
}


def _module_source_path(package_root: Path, module_name: str) -> Path:
    relative = Path(*module_name.split(".")[1:])
    package_file = package_root / relative / "__init__.py"
    candidates = [package_file]
    if relative.parts:
        candidates.append(package_root / relative.with_suffix(".py"))
    matches = [path.resolve(strict=True) for path in candidates if path.is_file()]
    assert len(matches) == 1, f"ambiguous/missing source owner for {module_name}: {matches}"
    return matches[0]


def _source_manifest() -> dict[str, object]:
    project_root = _project_root().resolve(strict=True)
    package_root = (project_root / "src" / "polisyos").resolve(strict=True)
    assert package_root.is_dir()
    modules = {}
    for module_name in _SOURCE_MODULE_NAMES + _CONSUMER_SOURCE_MODULES:
        path = _module_source_path(package_root, module_name)
        modules[module_name] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return {
        "profile": "source-checkout",
        "project_root": str(project_root),
        "package_root": str(package_root),
        "python_version": platform.python_version(),
        "python_version_info": list(sys.version_info[:3]),
        "executable": str(Path(sys.executable).resolve()),
        "modules": modules,
    }


def _run_child(
    entrypoint: str,
    *,
    prepend_import_paths: Sequence[str] = (),
    extra_env: Mapping[str, str] | None = None,
) -> None:
    manifest = _source_manifest()
    test_dir = str(Path(__file__).resolve().parent)
    candidate_src = str(Path(manifest["package_root"]).parent)
    paths = [
        *prepend_import_paths,
        test_dir,
        candidate_src,
        *(path for path in sys.path if path),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(paths))
    env[_SOURCE_MANIFEST_ENV] = json.dumps(manifest, sort_keys=True)
    if extra_env:
        env.update(extra_env)
    code = "from test_facade_runtime_reflection import " + entrypoint + "\n" + entrypoint + "()\n"
    result = subprocess.run(  # noqa: S603 -- fixed local test entrypoint only
        [sys.executable, "-B", "-c", code],
        cwd=_project_root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"{entrypoint} failed in a fresh interpreter\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    reports = []
    for line in result.stdout.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and "arm" in record:
            reports.append(record)
    assert len(reports) == 1, f"{entrypoint} did not emit one source record: {result.stdout}"
    sys.stdout.write(json.dumps(reports[0], sort_keys=True) + "\n")


def test_ordinary_supported_facades_resolve_full_reviewed_contract() -> None:
    _run_child("_fresh_facade_contract")


def test_consumer_first_import_resolves_the_same_contract() -> None:
    _run_child("_fresh_consumer_first_contract")


def test_removing_real_import_bindings_breaks_first_hint_resolution() -> None:
    _run_child("_binding_removal_negatives")


def test_semantic_mutants_are_rejected() -> None:
    _run_child("_semantic_mutant_negatives")


def test_same_byte_foreign_source_with_same_api_fails_origin_gate() -> None:
    _run_child("_same_byte_foreign_source_negative")


def _source_manifest_from_environment() -> dict[str, object]:
    raw = os.environ.get(_SOURCE_MANIFEST_ENV)
    assert raw is not None, "parent did not bind the source manifest before child startup"
    manifest = json.loads(raw)
    assert manifest["profile"] == "source-checkout"
    assert list(sys.version_info[:3]) == manifest["python_version_info"]
    assert platform.python_version() == manifest["python_version"]
    assert Path(sys.executable).resolve() == Path(manifest["executable"]).resolve()
    return manifest


def _assert_expected_module_origin(
    module_name: str, module: ModuleType, record: Mapping[str, str]
) -> None:
    expected_path = Path(record["path"]).resolve(strict=True)
    actual_file = Path(module.__file__).resolve(strict=True)
    actual_origin = Path(module.__spec__.origin).resolve(strict=True)
    assert actual_file == expected_path, (
        f"origin mismatch for {module_name}: expected candidate {expected_path}; "
        f"loaded {actual_file}"
    )
    assert actual_origin == expected_path, (
        f"spec origin mismatch for {module_name}: expected candidate {expected_path}; "
        f"loaded {actual_origin}"
    )
    actual_sha = hashlib.sha256(actual_file.read_bytes()).hexdigest()
    assert actual_sha == record["sha256"], (
        f"source bytes mismatch for {module_name} at {actual_file}: "
        f"expected {record['sha256']}; got {actual_sha}"
    )


def _assert_source_provenance(arm: str, module_names: Sequence[str]) -> None:
    import importlib

    manifest = _source_manifest_from_environment()
    loaded = {}
    for module_name in module_names:
        module = sys.modules.get(module_name)
        if module is None:
            module = importlib.import_module(module_name)
        record = manifest["modules"][module_name]
        _assert_expected_module_origin(module_name, module, record)
        loaded[module_name] = {"path": record["path"], "sha256": record["sha256"]}
    sys.stdout.write(
        json.dumps(
            {
                "arm": arm,
                "profile": manifest["profile"],
                "python_version": manifest["python_version"],
                "executable": manifest["executable"],
                "project_root": manifest["project_root"],
                "package_root": manifest["package_root"],
                "source_modules": loaded,
            },
            sort_keys=True,
        )
        + "\n"
    )


def _same_byte_foreign_source_negative() -> None:
    import importlib
    import importlib.abc
    import importlib.util
    import sys
    import tempfile

    manifest = _source_manifest_from_environment()
    foreign_names = (
        "polisyos.fabric",
        "polisyos.fabric.connectors",
        "polisyos.fabric.data_plane",
    )
    import polisyos

    _assert_expected_module_origin("polisyos", polisyos, manifest["modules"]["polisyos"])
    assert "polisyos.fabric" not in sys.modules

    with tempfile.TemporaryDirectory(prefix="fabric_same_byte_foreign_source_") as temp_root:
        fixture_root = Path(temp_root)
        foreign_records = {}
        finder_specs = {}
        for module_name in foreign_names:
            expected = manifest["modules"][module_name]
            candidate_path = Path(expected["path"]).resolve(strict=True)
            assert candidate_path.name == "__init__.py"
            candidate_bytes = candidate_path.read_bytes()
            candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()
            assert candidate_sha == expected["sha256"]

            relative_package = Path(*module_name.split(".")[1:])
            foreign_path = fixture_root / "polisyos" / relative_package / "__init__.py"
            foreign_path.parent.mkdir(parents=True, exist_ok=True)
            foreign_path.write_bytes(candidate_bytes)
            assert hashlib.sha256(foreign_path.read_bytes()).hexdigest() == candidate_sha

            finder_specs[module_name] = (foreign_path, candidate_path.parent)
            foreign_records[module_name] = {
                "path": str(foreign_path.resolve(strict=True)),
                "sha256": candidate_sha,
                "identical_candidate_bytes": True,
            }

        class SameByteForeignFacadeFinder(importlib.abc.MetaPathFinder):
            def __init__(self, specs: Mapping[str, tuple[Path, Path]]) -> None:
                self._specs = specs

            def find_spec(
                self,
                fullname: str,
                path: Sequence[str] | None = None,
                target: ModuleType | None = None,
            ) -> ModuleSpec | None:
                selected = self._specs.get(fullname)
                if selected is None:
                    return None
                foreign_path, candidate_package_path = selected
                return importlib.util.spec_from_file_location(
                    fullname,
                    foreign_path,
                    submodule_search_locations=[str(candidate_package_path)],
                )

        finder = SameByteForeignFacadeFinder(finder_specs)
        sys.meta_path.insert(0, finder)
        try:
            import polisyos.fabric as fabric
            import polisyos.fabric.connectors as connectors_api
            import polisyos.fabric.data_plane as data_plane_api
        finally:
            sys.meta_path.remove(finder)

        loaded_facades = {
            "polisyos.fabric": fabric,
            "polisyos.fabric.connectors": connectors_api,
            "polisyos.fabric.data_plane": data_plane_api,
        }
        for module_name, names in _SELECTED_PUBLIC_NAMES.items():
            module = loaded_facades[module_name]
            assert names <= set(module.__all__)

        import polisyos.fabric.connectors.cache.invalidation as invalidation
        import polisyos.fabric.evidence.decision_data as decision_data
        import polisyos.fabric.world.query as world_query

        # Identical copied facades resolve the same candidate owner objects and behavior.
        assert fabric.query_world_table is data_plane_api.query_world_table
        assert fabric.query_world_table is world_query.query_world_table
        assert fabric.TemporalRef is decision_data.TemporalRef
        assert fabric.WorldQueryRequest is world_query.WorldQueryRequest
        assert fabric.query_claims is world_query.query_claims
        assert fabric.query_events is world_query.query_events
        assert connectors_api.InvalidationTrigger is invalidation.InvalidationTrigger
        assert connectors_api.InvalidationOrchestrator is invalidation.InvalidationOrchestrator
        assert connectors_api.SchemaChangeInvalidationTrigger is (
            invalidation.SchemaChangeInvalidationTrigger
        )
        _assert_facade_contracts(fabric)

        for module_name in loaded_facades:
            with pytest.raises(AssertionError, match="origin mismatch"):
                _assert_source_provenance(
                    f"same-byte-foreign-{module_name}",
                    (module_name,),
                )

        candidate_owner_sources = {}
        candidate_owner_names = tuple(
            name for name in _SOURCE_MODULE_NAMES if name not in foreign_names
        )
        for module_name in candidate_owner_names:
            module = sys.modules.get(module_name)
            if module is None:
                module = importlib.import_module(module_name)
            expected = manifest["modules"][module_name]
            _assert_expected_module_origin(module_name, module, expected)
            candidate_owner_sources[module_name] = {
                "path": expected["path"],
                "sha256": expected["sha256"],
            }

        report = {
            "arm": "same-byte-foreign-source-counterexample",
            "profile": "source-checkout-self-generated-foreign-negative",
            "python_version": platform.python_version(),
            "executable": manifest["executable"],
            "selected_api_members_match": True,
            "full_reflection_contract": "PASS_ON_BYTE_IDENTICAL_FOREIGN_FACADES",
            "owner_type_identity": "PASS",
            "candidate_owner_modules": candidate_owner_sources,
            "foreign_facade_modules": foreign_records,
            "origin_gate": "rejected_all_three_by_candidate_path",
        }

    sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")


def _parameter(
    name: str,
    kind: inspect._ParameterKind = inspect.Parameter.POSITIONAL_OR_KEYWORD,
    default: object = inspect.Parameter.empty,
) -> tuple[str, inspect._ParameterKind, object]:
    return (name, kind, default)


def _assert_default(actual: object, expected: object) -> None:
    if expected is inspect.Parameter.empty:
        assert actual is inspect.Parameter.empty
    else:
        assert type(actual) is type(expected)
        assert actual == expected


def _assert_callable_contract(
    target: Callable[..., object],
    expected_parameters: Sequence[tuple[str, object, object]],
    expected_hints: Mapping[str, object],
    *,
    is_async: bool = False,
) -> None:
    from typing import get_type_hints

    signature = inspect.signature(target)
    actual_parameters = list(signature.parameters.values())
    expected_names = [name for name, _, _ in expected_parameters]
    actual_names = [parameter.name for parameter in actual_parameters]
    assert actual_names[: len(expected_names)] == expected_names

    for actual, (name, kind, default) in zip(
        actual_parameters[: len(expected_parameters)],
        expected_parameters,
        strict=True,
    ):
        assert actual.name == name
        assert actual.kind is kind
        _assert_default(actual.default, default)

    # Additive compatibility is limited to trailing optional, typed parameters.
    for parameter in actual_parameters[len(expected_parameters) :]:
        assert parameter.kind in {
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
        assert parameter.default is not inspect.Parameter.empty

    for parameter in actual_parameters:
        if parameter.annotation is inspect.Parameter.empty:
            assert parameter.name in {"self", "cls"}
    assert signature.return_annotation is not inspect.Signature.empty
    assert inspect.iscoroutinefunction(target) is is_async

    hints = get_type_hints(target, include_extras=True)
    declared_keys = {
        parameter.name
        for parameter in actual_parameters
        if parameter.annotation is not inspect.Parameter.empty
    }
    assert set(hints) == declared_keys | {"return"}
    assert set(expected_hints) <= set(hints)
    for name, expected in expected_hints.items():
        assert hints[name] == expected, f"{target!r}: {name!r} differs"


def _assert_dataclass_contract(
    target: type[object], expected_fields: Sequence[tuple[str, object, object]]
) -> None:
    from dataclasses import MISSING, fields
    from typing import get_type_hints

    actual_fields = list(fields(target))
    actual_names = [field.name for field in actual_fields]
    expected_names = [name for name, _, _ in expected_fields]
    assert actual_names[: len(expected_names)] == expected_names

    hints = get_type_hints(target, include_extras=True)
    assert set(hints) == set(actual_names)
    for name, expected_type, expected_default in expected_fields:
        assert hints[name] == expected_type, f"{target.__qualname__}.{name} differs"
        actual = next(field for field in actual_fields if field.name == name)
        if expected_default is MISSING:
            assert actual.default is MISSING
            assert actual.default_factory is MISSING
        else:
            assert actual.default_factory is MISSING
            assert type(actual.default) is type(expected_default)
            assert actual.default == expected_default

    # Future additive request fields must be typed and defaulted.
    for field in actual_fields[len(expected_fields) :]:
        assert field.name in hints
        assert field.default is not MISSING or field.default_factory is not MISSING


def _assert_facade_contracts(fabric: ModuleType) -> None:
    from typing import get_type_hints as resolve_hints

    import polisyos.fabric.connectors as supported_connectors
    import polisyos.fabric.data_plane as supported_data_plane
    import polisyos.fabric.data_plane.modes as documented_modes

    # Resolve before importing canonical expected types or deep owner modules.
    first_targets = (
        supported_connectors.InvalidationTrigger.check_for_updates,
        supported_connectors.InvalidationOrchestrator.__init__,
        supported_connectors.SchemaChangeInvalidationTrigger.__init__,
        supported_connectors.SchemaChangeInvalidationTrigger.on_contract_registered,
        fabric.TemporalRef.from_runtime_scope,
        fabric.query_world_table,
        fabric.query_claims,
        fabric.query_events,
        fabric.WorldQueryRequest,
        supported_data_plane.query_world_table,
        documented_modes.run_batch_incremental,
        documented_modes.run_record_mode,
        documented_modes.run_replay_mode,
        documented_modes.run_streaming_windowed,
    )
    for target in first_targets:
        resolve_hints(target, include_extras=True)

    from collections.abc import Iterable, Mapping, Sequence
    from dataclasses import MISSING
    from pathlib import Path
    from typing import Any, get_args, get_origin, get_type_hints

    import pandas as pd

    import polisyos.fabric.connectors as connectors_api
    import polisyos.fabric.connectors.cache.invalidation as invalidation
    import polisyos.fabric.data_plane as data_plane_api
    import polisyos.fabric.data_plane.modes as modes
    import polisyos.fabric.evidence.decision_data as decision_data
    import polisyos.fabric.world.query as world_query
    from polisyos.core.contracts.runtime import (
        TemporalRef as RuntimeTemporalRef,
    )
    from polisyos.core.contracts.runtime import (
        TemporalScope as RuntimeTemporalScope,
    )
    from polisyos.core.security import AccessScope, DatabaseBackend
    from polisyos.fabric.connectors.base import (
        ConnectionConfig,
        ConnectionHandle,
        SourceConnector,
        SourceConnectorInstance,
        SourceConnectorValue,
    )
    from polisyos.fabric.connectors.cache.store import ConnectorCacheStore
    from polisyos.fabric.connectors.contracts import ConnectorSchemaContract, EvolutionReport
    from polisyos.fabric.data_plane.orchestrator import IngestionResult
    from polisyos.fabric.evidence.decision_data import _RuntimeTemporalScopeLike
    from polisyos.fabric.io.db import SimulationDB
    from polisyos.fabric.security import DataClassification, JsonlAccessAuditLog, RowAccessPolicy
    from polisyos.ir.connectors import DataVersion

    assert fabric.__spec__ is not None
    assert Path(fabric.__spec__.origin).is_file()
    assert connectors_api.InvalidationTrigger is invalidation.InvalidationTrigger
    assert connectors_api.InvalidationOrchestrator is invalidation.InvalidationOrchestrator
    assert connectors_api.SchemaChangeInvalidationTrigger is (
        invalidation.SchemaChangeInvalidationTrigger
    )

    connector_alias = SourceConnectorValue[Any]
    assert get_origin(connector_alias) is SourceConnectorValue
    assert get_args(connector_alias) == (Any,)
    alias_parameters = SourceConnectorValue.__type_params__
    assert len(alias_parameters) == 1
    alias_parameter = alias_parameters[0]
    assert SourceConnectorValue.__value__ == (
        SourceConnector[alias_parameter] | SourceConnectorInstance[alias_parameter]
    )

    cache_store = ConnectorCacheStore
    none_type = type(None)
    invalidation_contracts = [
        (
            connectors_api.InvalidationTrigger.check_for_updates,
            [
                _parameter("self"),
                _parameter("connector"),
                _parameter("handle"),
                _parameter("dataset_id"),
                _parameter("cached_version"),
                _parameter("cached_metadata", default=None),
            ],
            {
                "connector": connector_alias,
                "handle": ConnectionHandle,
                "dataset_id": str,
                "cached_version": DataVersion | None,
                "cached_metadata": dict[str, Any] | None,
                "return": invalidation.InvalidationEvent | None,
            },
            True,
        ),
        (
            connectors_api.SchemaChangeInvalidationTrigger.__init__,
            [_parameter("self"), _parameter("cache_store")],
            {"cache_store": cache_store, "return": none_type},
            False,
        ),
        (
            connectors_api.SchemaChangeInvalidationTrigger.on_contract_registered,
            [_parameter("self"), _parameter("contract"), _parameter("report")],
            {
                "contract": ConnectorSchemaContract,
                "report": EvolutionReport | None,
                "return": int,
            },
            False,
        ),
        (
            connectors_api.InvalidationOrchestrator.__init__,
            [
                _parameter("self"),
                _parameter("cache"),
                _parameter("registry"),
                _parameter("trigger", default=None),
            ],
            {
                "cache": cache_store,
                "registry": invalidation._ConnectorRegistry,
                "trigger": invalidation.InvalidationTrigger | None,
                "return": none_type,
            },
            False,
        ),
    ]
    for target, parameters, hints, is_async in invalidation_contracts:
        _assert_callable_contract(target, parameters, hints, is_async=is_async)

    temporal_descriptor = inspect.getattr_static(fabric.TemporalRef, "from_runtime_scope")
    assert isinstance(temporal_descriptor, classmethod)
    _assert_callable_contract(
        fabric.TemporalRef.from_runtime_scope,
        [_parameter("scope")],
        {
            "scope": (
                RuntimeTemporalScope
                | RuntimeTemporalRef
                | _RuntimeTemporalScopeLike
                | Mapping[str, object]
                | None
            ),
            "return": decision_data.TemporalRef | None,
        },
    )

    assert fabric.TemporalRef is decision_data.TemporalRef
    assert fabric.WorldQueryRequest is world_query.WorldQueryRequest
    assert fabric.query_world_table is world_query.query_world_table
    assert fabric.query_claims is world_query.query_claims
    assert fabric.query_events is world_query.query_events
    assert data_plane_api.query_world_table is world_query.query_world_table
    assert "query_world_table" in data_plane_api.__all__

    query_security_parameters = [
        _parameter("allowed_columns", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("access_scope", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("classification", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("column_classification", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("purpose_of_use", inspect.Parameter.KEYWORD_ONLY, ""),
        _parameter("row_policy", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("tenant_column", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("audit_log", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("as_of_tx_time", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("as_of_valid_time", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("snapshot_root", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("snapshot_id", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("branch", inspect.Parameter.KEYWORD_ONLY, None),
    ]
    query_security_hints = {
        "allowed_columns": Sequence[str] | None,
        "access_scope": AccessScope | None,
        "classification": DataClassification | str | None,
        "column_classification": Mapping[str, DataClassification | str] | None,
        "purpose_of_use": str,
        "row_policy": RowAccessPolicy | None,
        "tenant_column": str | None,
        "audit_log": JsonlAccessAuditLog | None,
        "as_of_tx_time": str | None,
        "as_of_valid_time": str | int | None,
        "snapshot_root": str | Path | None,
        "snapshot_id": str | None,
        "branch": str | None,
    }

    _assert_callable_contract(
        fabric.query_world_table,
        [
            _parameter("db"),
            _parameter("table", inspect.Parameter.KEYWORD_ONLY),
            _parameter("columns", inspect.Parameter.KEYWORD_ONLY, None),
            _parameter("where", inspect.Parameter.KEYWORD_ONLY, None),
            _parameter("order_by", inspect.Parameter.KEYWORD_ONLY, None),
            _parameter("limit", inspect.Parameter.KEYWORD_ONLY, 1_000),
            *query_security_parameters,
        ],
        {
            "db": SimulationDB | DatabaseBackend,
            "table": str,
            "columns": Sequence[str] | None,
            "where": Mapping[str, Any] | None,
            "order_by": Iterable[str] | None,
            "limit": int,
            **query_security_hints,
            "return": pd.DataFrame,
        },
    )

    claims_events_parameters = [
        _parameter("db"),
        _parameter("where", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("columns", inspect.Parameter.KEYWORD_ONLY, None),
        _parameter("limit", inspect.Parameter.KEYWORD_ONLY, 1_000),
        *query_security_parameters,
    ]
    claims_events_hints = {
        "db": SimulationDB | DatabaseBackend,
        "where": Mapping[str, Any] | None,
        "columns": Sequence[str] | None,
        "limit": int,
        **query_security_hints,
        "return": pd.DataFrame,
    }
    _assert_callable_contract(fabric.query_claims, claims_events_parameters, claims_events_hints)
    _assert_callable_contract(fabric.query_events, claims_events_parameters, claims_events_hints)

    request_fields = [
        ("table", str, MISSING),
        ("columns", tuple[str, ...], ("*",)),
        ("where", Mapping[str, Any] | None, None),
        ("order_by", tuple[str, ...], ()),
        ("limit", int, 1_000),
        ("allowed_columns", tuple[str, ...] | None, None),
        ("access_scope", AccessScope | None, None),
        ("classification", DataClassification | str | None, None),
        ("column_classification", Mapping[str, DataClassification | str] | None, None),
        ("purpose_of_use", str, ""),
        ("row_policy", RowAccessPolicy | None, None),
        ("tenant_column", str | None, None),
        ("audit_log", JsonlAccessAuditLog | None, None),
        ("as_of_tx_time", str | None, None),
        ("as_of_valid_time", str | int | None, None),
        ("snapshot_root", str | Path | None, None),
        ("snapshot_id", str | None, None),
        ("branch", str | None, None),
    ]
    _assert_dataclass_contract(fabric.WorldQueryRequest, request_fields)

    expected_connection_config = ConnectionConfig | dict[str, object] | None
    mode_returns = {
        "run_batch_incremental": IngestionResult,
        "run_streaming_windowed": IngestionResult,
        "run_record_mode": tuple[IngestionResult, str],
        "run_replay_mode": IngestionResult,
    }
    for name, expected_return in mode_returns.items():
        target = getattr(modes, name)
        signature = inspect.signature(target)
        parameter = signature.parameters["connection_config"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is None
        assert name not in data_plane_api.__all__
        hints = get_type_hints(target, include_extras=True)
        assert hints["connection_config"] == expected_connection_config
        assert hints["return"] == expected_return
        assert set(signature.parameters) <= set(hints)

    assert all(name not in fabric.__all__ for name in mode_returns)


def _fresh_facade_contract() -> None:
    import polisyos.fabric as fabric

    _assert_facade_contracts(fabric)
    _assert_source_provenance("facade-first", _SOURCE_MODULE_NAMES)


def _fresh_consumer_first_contract() -> None:
    import sys
    import tempfile

    assert "polisyos.fabric" not in sys.modules

    import polisyos.runtime.quality.world_model_record as consumer

    with tempfile.TemporaryDirectory(prefix="fabric_reflection_consumer_first_") as root:
        reference = consumer.FabricWorldRef(
            snapshot_root=root,
            snapshot_id="missing-snapshot",
            branch="main",
            world_query_policy="read_only",
            provenance_manifest_ref="fixture:reflection-oracle",
        )
        with pytest.raises(consumer.WorldModelRecordError) as error_info:
            consumer._resolve_fabric_world_ref(reference)
        assert error_info.value.code == "fabric_world_snapshot_unresolved"
    assert "polisyos.fabric" in sys.modules
    _assert_facade_contracts(sys.modules["polisyos.fabric"])
    _assert_source_provenance(
        "consumer-first",
        _SOURCE_MODULE_NAMES + _CONSUMER_SOURCE_MODULES,
    )


def _binding_removal_negatives() -> None:
    import importlib
    from typing import get_type_hints

    import polisyos.fabric as fabric

    assert fabric.__spec__ is not None
    cases = [
        (
            "polisyos.fabric.connectors.cache.invalidation",
            "SourceConnectorValue",
            "polisyos.fabric.connectors.cache.invalidation",
            "InvalidationTrigger.check_for_updates",
        ),
        (
            "polisyos.fabric.connectors.cache.invalidation",
            "ConnectorCacheStore",
            "polisyos.fabric.connectors.cache.invalidation",
            "SchemaChangeInvalidationTrigger.__init__",
        ),
        (
            "polisyos.fabric.connectors.cache.invalidation",
            "_ConnectorRegistry",
            "polisyos.fabric.connectors.cache.invalidation",
            "InvalidationOrchestrator.__init__",
        ),
        (
            "polisyos.fabric.evidence.decision_data",
            "RuntimeTemporalRef",
            "polisyos.fabric.evidence.decision_data",
            "TemporalRef.from_runtime_scope",
        ),
        (
            "polisyos.fabric.world.query",
            "SimulationDB",
            "polisyos.fabric.world.query",
            "query_world_table",
        ),
        (
            "polisyos.fabric.data_plane.modes",
            "ConnectionConfig",
            "polisyos.fabric.data_plane.modes",
            "run_batch_incremental",
        ),
    ]
    for owner_name, binding_name, target_module_name, target_path in cases:
        owner = importlib.import_module(owner_name)
        target_module = importlib.import_module(target_module_name)
        value = owner.__dict__.pop(binding_name)
        try:
            target = target_module
            for part in target_path.split("."):
                target = getattr(target, part)
            with pytest.raises(NameError, match=binding_name):
                get_type_hints(target, include_extras=True)
        finally:
            owner.__dict__[binding_name] = value
    _assert_source_provenance("exact-binding-removal-negative", _TARGET_SOURCE_MODULES)


def _must_reject(assertion: Callable[[], object]) -> None:
    try:
        assertion()
    except AssertionError:
        return
    raise AssertionError("the independent reflection oracle accepted a semantic mutant")


def _clone_function(function: FunctionType, annotations: Mapping[str, object]) -> FunctionType:
    clone = FunctionType(
        function.__code__,
        function.__globals__,
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    clone.__kwdefaults__ = function.__kwdefaults__
    clone.__annotations__ = annotations
    return clone


def _semantic_mutant_negatives() -> None:
    from collections.abc import Mapping
    from dataclasses import MISSING
    from typing import Any

    import polisyos.fabric.connectors.cache.invalidation as invalidation
    import polisyos.fabric.evidence.decision_data as decision_data
    import polisyos.fabric.world.query as world_query
    from polisyos.core.contracts.runtime import (
        TemporalRef as RuntimeTemporalRef,
    )
    from polisyos.core.contracts.runtime import (
        TemporalScope as RuntimeTemporalScope,
    )
    from polisyos.fabric.connectors.base import (
        ConnectionHandle,
        SourceConnector,
        SourceConnectorInstance,
        SourceConnectorValue,
    )
    from polisyos.fabric.connectors.cache.store import ConnectorCacheStore
    from polisyos.fabric.evidence.decision_data import _RuntimeTemporalScopeLike
    from polisyos.ir.connectors import DataVersion

    invalidation_function = invalidation.InvalidationTrigger.check_for_updates
    invalidation_parameters = [
        _parameter("self"),
        _parameter("connector"),
        _parameter("handle"),
        _parameter("dataset_id"),
        _parameter("cached_version"),
        _parameter("cached_metadata", default=None),
    ]
    invalidation_hints = {
        "connector": SourceConnectorValue[Any],
        "handle": ConnectionHandle,
        "dataset_id": str,
        "cached_version": DataVersion | None,
        "cached_metadata": dict[str, Any] | None,
        "return": invalidation.InvalidationEvent | None,
    }

    def invalidation_clone(
        changes: Mapping[str, object] | None = None, remove: str | None = None
    ) -> FunctionType:
        annotations = dict(invalidation_function.__annotations__)
        if changes:
            annotations.update(changes)
        if remove:
            del annotations[remove]
        return _clone_function(invalidation_function, annotations)

    _must_reject(
        lambda: _assert_callable_contract(
            invalidation_clone({"connector": Any}),
            invalidation_parameters,
            invalidation_hints,
            is_async=True,
        )
    )
    _must_reject(
        lambda: _assert_callable_contract(
            invalidation_clone({"connector": ConnectionHandle}),
            invalidation_parameters,
            invalidation_hints,
            is_async=True,
        )
    )
    _must_reject(
        lambda: _assert_callable_contract(
            invalidation_clone(remove="cached_version"),
            invalidation_parameters,
            invalidation_hints,
            is_async=True,
        )
    )
    _must_reject(
        lambda: _assert_callable_contract(
            invalidation_clone(
                {"connector": (SourceConnector[Any] | SourceConnectorInstance[Any])}
            ),
            invalidation_parameters,
            invalidation_hints,
            is_async=True,
        )
    )

    constructor = invalidation.SchemaChangeInvalidationTrigger.__init__
    constructor_probe = _clone_function(constructor, dict(constructor.__annotations__))
    constructor_probe.__signature__ = inspect.signature(constructor).replace(
        parameters=[
            parameter
            for parameter in inspect.signature(constructor).parameters.values()
            if parameter.name != "cache_store"
        ]
    )
    _must_reject(
        lambda: _assert_callable_contract(
            constructor_probe,
            [_parameter("self"), _parameter("cache_store")],
            {"cache_store": ConnectorCacheStore, "return": type(None)},
        )
    )

    orchestrator = invalidation.InvalidationOrchestrator.__init__
    missing_registry = dict(orchestrator.__annotations__)
    del missing_registry["registry"]
    _must_reject(
        lambda: _assert_callable_contract(
            _clone_function(orchestrator, missing_registry),
            [
                _parameter("self"),
                _parameter("cache"),
                _parameter("registry"),
                _parameter("trigger", default=None),
            ],
            {
                "cache": ConnectorCacheStore,
                "registry": invalidation._ConnectorRegistry,
                "trigger": invalidation.InvalidationTrigger | None,
                "return": type(None),
            },
        )
    )

    temporal_method = decision_data.TemporalRef.__dict__["from_runtime_scope"]
    temporal_function = temporal_method.__func__
    temporal_annotations = dict(temporal_function.__annotations__)
    temporal_annotations["scope"] = (
        RuntimeTemporalScope | _RuntimeTemporalScopeLike | Mapping[str, object] | None
    )
    temporal_probe = classmethod(_clone_function(temporal_function, temporal_annotations)).__get__(
        None, decision_data.TemporalRef
    )
    _must_reject(
        lambda: _assert_callable_contract(
            temporal_probe,
            [_parameter("scope")],
            {
                "scope": (
                    RuntimeTemporalScope
                    | RuntimeTemporalRef
                    | _RuntimeTemporalScopeLike
                    | Mapping[str, object]
                    | None
                ),
                "return": decision_data.TemporalRef | None,
            },
        )
    )

    class_probe = world_query.WorldQueryRequest
    original_fields = class_probe.__dataclass_fields__
    try:
        class_probe.__dataclass_fields__ = {
            name: field for name, field in original_fields.items() if name != "table"
        }
        _must_reject(
            lambda: _assert_dataclass_contract(
                class_probe,
                [("table", str, MISSING)],
            )
        )
    finally:
        class_probe.__dataclass_fields__ = original_fields

    original_annotations = class_probe.__annotations__
    try:
        class_probe.__annotations__ = {
            name: annotation for name, annotation in original_annotations.items() if name != "table"
        }
        _must_reject(
            lambda: _assert_dataclass_contract(
                class_probe,
                [("table", str, MISSING)],
            )
        )
    finally:
        class_probe.__annotations__ = original_annotations
    _assert_source_provenance("semantic-mutation-negative", _SEMANTIC_SOURCE_MODULES)
