"""Collect source execution evidence for an already appointed Python process.

This module is an evidence producer, not an authority issuer. Its input mapping
must be independently derived from the selected source snapshot by the host and
reconciled by the confidence-ledger owner. Constructing a recorder, providing a
mapping, or serializing its output cannot appoint a runtime profile or establish
policy authority. It deliberately does not claim material-state completeness or
protection through a later decision.
"""

from __future__ import annotations

import _imp
import builtins
import hashlib
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
import sys
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from types import (
    CellType,
    CodeType,
    FrameType,
    FunctionType,
    GetSetDescriptorType,
    MappingProxyType,
    ModuleType,
)
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

_COMPILE = compile
_EXEC = exec
_PATH_FINDER = importlib.machinery.PathFinder
_PATH_FINDER_DESCRIPTOR = type.__getattribute__(_PATH_FINDER, "__dict__")["find_spec"]
_FIND_SPEC = _PATH_FINDER.find_spec
_SOURCE_LOADER = importlib.machinery.SourceFileLoader
_GETPID = os.getpid
_PROCESS_CAPTURE: SourceExecutionCapture | None = None
_PROCESS_OWNER_SLOT = "_polisyos_loaded_execution_owner_v1"
_MISSING = object()


def _passive_lookup(mapping: object, key: str) -> tuple[bool, object]:
    """Find an exact string key without invoking candidate hash/equality hooks."""

    if type(mapping) not in (dict, MappingProxyType) or type(key) is not str:
        return False, None
    try:
        for candidate, value in mapping.items():
            if type(candidate) is str and candidate == key:
                return True, value
    except RuntimeError:
        # A concurrent mutation cannot establish a passive read.
        return False, None
    return False, None


def _passive_binding_matches(mapping: object, key: str, expected: object) -> bool:
    """Require the exact binding to be present, including a held None value."""

    found, actual = _passive_lookup(mapping, key)
    return found and actual is expected


def _finder_descriptor_functions(value: object) -> tuple[FunctionType, ...] | None:
    """Read supported descriptor representations without invoking them."""

    if type(value) is FunctionType:
        return (value,)
    if type(value) is property:
        return cast(
            "tuple[FunctionType, ...]",
            tuple(
                function
                for function in (value.fget, value.fset, value.fdel)
                if function is not None
            ),
        )
    if type(value) is classmethod:
        return (cast("FunctionType", value.__func__),)
    if type(value) is staticmethod:
        return (cast("FunctionType", value.__func__),)
    return None


def _finder_callable_hold(function: FunctionType) -> tuple[object, ...] | None:
    """Retain callable bindings without invoking descriptors or callbacks."""

    kwdefaults = function.__kwdefaults__
    if kwdefaults is not None and (
        type(kwdefaults) is not dict or any(type(key) is not str for key in kwdefaults)
    ):
        return None
    closure = function.__closure__
    cells: list[tuple[object, bool, object]] = []
    for cell in closure or ():
        try:
            cells.append((cell, True, cell.cell_contents))
        except ValueError:
            cells.append((cell, False, None))
    return (
        function,
        function.__code__,
        function.__defaults__,
        kwdefaults,
        () if kwdefaults is None else tuple(kwdefaults.items()),
        closure,
        tuple(cells),
    )


def _finder_callable_unchanged(held: tuple[object, ...]) -> bool:
    if len(held) != 7:
        return False
    function = held[0]
    if type(function) is not FunctionType:
        return False
    _, code, defaults, kwdefaults, kwitems, closure, cells = held
    if (
        function.__code__ is not code
        or function.__defaults__ is not defaults
        or function.__kwdefaults__ is not kwdefaults
        or function.__closure__ is not closure
        or type(kwitems) is not tuple
        or type(cells) is not tuple
    ):
        return False
    if kwdefaults is None:
        if kwitems:
            return False
    elif (
        type(kwdefaults) is not dict
        or len(kwdefaults) != len(kwitems)
        or any(type(key) is not str for key in kwdefaults)
        or any(
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or not _passive_binding_matches(kwdefaults, item[0], item[1])
            for item in kwitems
        )
    ):
        return False
    if closure is None:
        return not cells
    if type(closure) is not tuple or len(closure) != len(cells):
        return False
    for cell, prior in zip(closure, cells, strict=True):
        if (
            type(cell) is not CellType
            or type(prior) is not tuple
            or len(prior) != 3
            or prior[0] is not cell
            or type(prior[1]) is not bool
        ):
            return False
        try:
            value = cell.cell_contents
        except ValueError:
            if prior[1]:
                return False
        else:
            if not prior[1] or value is not prior[2]:
                return False
    return True


class CaptureError(ImportError):
    """Source execution evidence could not be collected or retained."""


@dataclass(frozen=True, slots=True)
class ExpectedSource:
    """One externally selected source path and exact SHA-256 content digest."""

    relative_path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ModuleExecution:
    """A completed initializer and its retained live execution objects."""

    module_name: str
    relative_path: str
    source_sha256: str
    code: CodeType
    module: ModuleType
    loader: _CapturedSourceLoader
    spec: importlib.machinery.ModuleSpec
    origin: str
    package: str
    search_locations: tuple[str, ...] | None
    package_search_locations: tuple[str, ...] | None
    watched_exports: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ImportEvidence:
    """A successful import observed at a selected source-owned call site."""

    importer_name: str
    importer: ModuleType
    caller_code: CodeType
    caller_line: int
    provider_name: str
    provider: ModuleType
    returned: ModuleType
    requested_exports: tuple[str, ...]
    retained_exports: Mapping[str, object]
    unresolved_exports: tuple[str, ...]
    route: Literal["builtin_import", "import_module"]


@dataclass(frozen=True, slots=True)
class FailedImportEvidence:
    """A source-owned attempted import that did not return a provider."""

    importer_name: str
    importer: ModuleType
    caller_code: CodeType
    provider_name: str | None
    route: Literal["builtin_import", "import_module"]


@dataclass(frozen=True, slots=True)
class _SourceFinderClass:
    """One source-executed class in the selected finder method's MRO."""

    cls: type[object]
    owner: ModuleType
    owner_name: str
    class_name: str
    source_code: CodeType
    bases: tuple[type[object], ...]
    fields: tuple[tuple[str, object], ...]
    functions: tuple[tuple[object, ...], ...]


@dataclass(frozen=True, slots=True)
class _SourceOwnedFinder:
    """A finder and its source-executed method-resolution path."""

    finder: object
    finder_type: type[object]
    resolution_order: tuple[type[object], ...]
    classes: tuple[_SourceFinderClass, ...]
    method: FunctionType
    method_code: CodeType
    instance_namespace: dict[str, object]
    instance_fields: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class RelevantGraphDiagnostic:
    """A reachable event graph, without a completeness or authority claim."""

    roots: tuple[str, ...]
    reached_sources: tuple[str, ...]
    external_providers: tuple[str, ...]
    failed_imports: tuple[tuple[str, str | None], ...]
    failed_modules: tuple[tuple[str, str], ...]
    unresolved_importers: tuple[tuple[str, str], ...]
    pending_modules: tuple[str, ...]
    status: Literal["not_established"] = "not_established"


_IMPORT_EVENT_FIELDS = (
    "importer_name",
    "importer",
    "caller_code",
    "caller_line",
    "provider_name",
    "provider",
    "returned",
    "requested_exports",
    "retained_exports",
    "unresolved_exports",
    "route",
)

_EXECUTION_FIELDS = (
    "module_name",
    "relative_path",
    "source_sha256",
    "code",
    "module",
    "loader",
    "spec",
    "origin",
    "package",
    "search_locations",
    "package_search_locations",
    "watched_exports",
)


@dataclass(frozen=True, slots=True)
class SourceCaptureDiagnostic:
    """Compact evidence-only report; it cannot create a live admission."""

    schema_version: Literal["policyos.runtime.confidence_ledger.source_capture_diagnostic.v1"]
    proof_schema: Literal["policyos.runtime.confidence_ledger.loaded_execution_capture.v1"]
    identity_rule: Literal["canonical-source-execution/1"]
    status: Literal["not_established"]
    phase: Literal["new", "collecting", "failed"]
    runtime_profile_id: None
    first_unestablished_premise: Literal["appointed_profile"]
    failed_premise: str | None
    failure_code: str | None
    selected_source_count: int
    completed_module_count: int
    captured_source_projection_sha256: str | None
    provider_projection_sha256: None
    capture_time_role: Literal["in_progress_or_unavailable"]
    currentness_time_role: Literal["not_evaluated"]
    unresolved_by_construction: tuple[str, ...]


class _CapturedSourceLoader(_SOURCE_LOADER):
    """Execute exactly the bytes admitted by the producer's source input."""

    def __init__(
        self,
        name: str,
        path: str,
        capture: SourceExecutionCapture,
        expected: ExpectedSource,
    ) -> None:
        super().__init__(name, path)
        self._capture = capture
        self._expected = expected

    def exec_module(self, module: ModuleType) -> None:
        attributes = object.__getattribute__(self, "__dict__")
        _, capture = _passive_lookup(attributes, "_capture")
        _, expected = _passive_lookup(attributes, "_expected")
        _, name = _passive_lookup(attributes, "name")
        _, origin = _passive_lookup(attributes, "path")
        if type(capture) is not SourceExecutionCapture:
            return _SOURCE_LOADER.exec_module(self, module)
        if type(expected) is not ExpectedSource:
            capture._fail("loader_binding_invalid")
            return _SOURCE_LOADER.exec_module(self, module)
        if type(name) is not str or type(origin) is not str:
            capture._fail("module_initialization_invalid")
            return _SOURCE_LOADER.exec_module(self, module)
        try:
            capture._begin(name, module, self)
        except CaptureError:
            capture._module_fail(name, "module_initialization_invalid")
            return _SOURCE_LOADER.exec_module(self, module)
        try:
            source = Path(origin).read_bytes()
        except OSError:
            capture._module_fail(name, "selected_source_unavailable")
            return _SOURCE_LOADER.exec_module(self, module)
        source_sha256 = hashlib.sha256(source).hexdigest()
        if type(expected.sha256) is not str or source_sha256 != expected.sha256:
            capture._module_fail(name, "selected_source_bytes_mismatch")
            return _SOURCE_LOADER.exec_module(self, module)
        try:
            code = _COMPILE(
                source,
                origin,
                "exec",
                dont_inherit=True,
                optimize=sys.flags.optimize,
            )
            capture._bind_initialization_code(name, module, code)
            _EXEC(code, module.__dict__)
        except BaseException:
            capture._module_fail(name, "module_initialization_failed")
            raise
        try:
            capture._complete(name, module, self, source_sha256, code)
        except Exception:
            # The initializer already ran normally. Do not run it twice or
            # turn an evidence failure into a candidate-import failure.
            capture._module_fail(name, "module_observation_incomplete")


_CAPTURED_LOADER_TYPE = _CapturedSourceLoader
_CAPTURED_LOADER_INIT = _CapturedSourceLoader.__init__
_CAPTURED_LOADER_EXEC = _CapturedSourceLoader.exec_module


def _captured_loader_intact() -> bool:
    """Check the producer's retained loader implementation without invoking it."""

    return bool(
        _CapturedSourceLoader is _CAPTURED_LOADER_TYPE
        and type.__getattribute__(_CAPTURED_LOADER_TYPE, "__dict__").get("__init__")
        is _CAPTURED_LOADER_INIT
        and type.__getattribute__(_CAPTURED_LOADER_TYPE, "__dict__").get("exec_module")
        is _CAPTURED_LOADER_EXEC
    )


class _CaptureFinder(importlib.abc.MetaPathFinder):
    """Select standard source loaders while preserving Python import locking."""

    def __init__(self, capture: SourceExecutionCapture) -> None:
        self._capture = capture

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        capture = self._capture
        if fullname.partition(".")[0] not in capture._package_roots:
            return None
        if not capture._same_process():
            capture._fail("capture_inherited_across_fork")
            return None
        if capture.failed:
            # Candidate imports may continue, but this process can never promote
            # the failed capture into authority.
            return None
        if fullname in capture._module_failures:
            # A later import can still serve candidate work through normal
            # Python loading. Its original failure remains sticky evidence and
            # cannot be promoted by that later unrecorded execution.
            return None
        if not _captured_loader_intact():
            # Preserve the failure for this source even if the class is later
            # restored and Python removes or reimports the candidate module.
            capture._module_fail(fullname, "capture_loader_changed")
            return None
        if target is not None:
            capture._module_fail(fullname, "module_reload_not_admitted")
            return None
        expected = capture._sources.get(fullname)
        if expected is None:
            capture._module_fail(fullname, "module_source_not_selected")
            return None
        spec = _FIND_SPEC(fullname, path, target)
        if type(spec) is not importlib.machinery.ModuleSpec:
            capture._module_fail(fullname, "module_loader_not_admitted")
            return None
        spec_fields = object.__getattribute__(spec, "__dict__")
        _, spec_loader = _passive_lookup(spec_fields, "loader")
        _, spec_origin = _passive_lookup(spec_fields, "origin")
        _, spec_name = _passive_lookup(spec_fields, "name")
        if (
            type(spec_loader) is not _SOURCE_LOADER
            or type(spec_origin) is not str
            or type(spec_name) is not str
            or spec_name != fullname
        ):
            capture._module_fail(fullname, "module_loader_not_admitted")
            return None
        try:
            selected = capture._selected_path(expected)
            actual = Path(spec_origin).resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            capture._module_fail(fullname, "module_origin_not_admitted")
            return None
        if actual != selected:
            capture._module_fail(fullname, "module_origin_not_admitted")
            return None
        spec.origin = str(selected)
        spec.loader = _CapturedSourceLoader(fullname, str(selected), capture, expected)
        return spec


class _ExternalCaptureFinder(importlib.abc.MetaPathFinder):
    """Capture locked source during PathFinder's ordinary lookup."""

    def __init__(self, capture: SourceExecutionCapture) -> None:
        self._capture = capture

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        capture = self._capture
        selector = capture._external_source_selector
        if (
            selector is None
            or capture._selecting_external
            or capture.failed
            or not capture._same_process()
            or fullname.partition(".")[0] in capture._package_roots
            or fullname in capture._module_failures
        ):
            return _FIND_SPEC(fullname, path, target)
        if target is not None:
            if fullname in capture._sources:
                capture._module_fail(fullname, "module_reload_not_admitted")
            return _FIND_SPEC(fullname, path, target)
        spec = _FIND_SPEC(fullname, path, target)
        if type(spec) is not importlib.machinery.ModuleSpec:
            return spec
        fields = object.__getattribute__(spec, "__dict__")
        loader = _passive_lookup(fields, "loader")[1]
        origin = _passive_lookup(fields, "origin")[1]
        name = _passive_lookup(fields, "name")[1]
        if (
            type(loader) is not _SOURCE_LOADER
            or type(origin) is not str
            or type(name) is not str
            or name != fullname
        ):
            return spec
        capture._selecting_external = True
        try:
            selection = selector(fullname, origin)
        except Exception:
            capture._module_fail(fullname, "external_source_selection_failed")
            return spec
        finally:
            capture._selecting_external = False
        if selection is None:
            return spec
        if (
            type(selection) is not tuple
            or len(selection) != 2
            or type(selection[0]) is not str
            or type(selection[1]) is not str
            or len(selection[1]) != 64
            or any(char not in "0123456789abcdef" for char in selection[1])
            or not _captured_loader_intact()
        ):
            capture._module_fail(fullname, "external_source_selection_invalid")
            return spec
        expected = ExpectedSource(*selection)
        try:
            selected = capture._selected_path(expected)
            actual = Path(origin).resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            capture._module_fail(fullname, "module_origin_not_admitted")
            return spec
        if actual != selected:
            capture._module_fail(fullname, "module_origin_not_admitted")
            return spec
        previous = capture._sources.get(fullname)
        if previous is not None:
            if (
                fullname in capture._pending
                or fullname in capture._completed
                or previous.relative_path != expected.relative_path
                or previous.sha256 != expected.sha256
            ):
                capture._module_fail(fullname, "module_reload_not_admitted")
                return spec
            # find_spec can select source during preflight without executing it.
            # Preserve that exact held selection when the first import follows.
            expected = previous
        else:
            capture._selected_sources[fullname] = expected
        spec.origin = str(selected)
        spec.loader = _CapturedSourceLoader(fullname, str(selected), capture, expected)
        return spec


class SourceExecutionCapture:
    """Retain completed source executions under a caller-supplied source selection.

    Installation is valid only before any selected top-level package is loaded.
    A failed installation is process-terminal; initializer failure is sticky for
    the affected module and any reachable graph, not unrelated graphs. A live
    process slot prevents a second producer instance from restarting capture.
    The host must retain and reconcile the actual slot and producer bindings.
    This primitive does
    not authenticate the caller-supplied selection, interpreter, third-party
    providers, material state, or later mutation ownership.
    """

    def __init__(
        self,
        root: Path,
        sources: Mapping[str, ExpectedSource],
        *,
        exports: Mapping[str, set[str] | frozenset[str]] | None = None,
        external_source_selector: Callable[[str, str], tuple[str, str] | None] | None = None,
    ) -> None:
        self._root = root.resolve(strict=True)
        self._process_id = _GETPID()
        if (
            type(sources) not in (dict, MappingProxyType)
            or not sources
            or any(
                type(name) is not str
                or not name
                or any(not part.isidentifier() for part in name.split("."))
                for name in sources
            )
        ):
            raise ValueError("capture_source_selection_invalid")
        self._selected_sources = dict(sources)
        self._sources = MappingProxyType(self._selected_sources)
        self._external_source_selector = external_source_selector
        self._selecting_external = False
        if exports is not None and (
            type(exports) not in (dict, MappingProxyType)
            or any(
                type(name) is not str
                or type(names) not in (set, frozenset)
                or any(type(export) is not str or not export.isidentifier() for export in names)
                for name, names in exports.items()
            )
        ):
            raise ValueError("capture_export_selection_invalid")
        self._exports = MappingProxyType(
            {name: frozenset(names) for name, names in (exports or {}).items()}
        )
        self._package_roots = frozenset(name.partition(".")[0] for name in self._sources)
        self._finder = _CaptureFinder(self)
        self._external_finder = (
            _ExternalCaptureFinder(self) if external_source_selector is not None else None
        )
        self._path_finder_descriptor: object | None = None
        self._initial_meta_path: tuple[object, ...] = ()
        self._meta_path_object: list[object] | None = None
        self._admitted_meta_path: tuple[object, ...] = ()
        self._source_owned_finders: dict[int, _SourceOwnedFinder] = {}
        self._phase: Literal["new", "collecting", "failed"] = "new"
        self._failure: str | None = None
        self._pending: dict[str, ModuleType] = {}
        self._pending_codes: dict[str, CodeType] = {}
        self._completed: dict[str, ModuleExecution] = {}
        self._execution_anchors: dict[str, tuple[object, ...]] = {}
        self._module_failures: dict[str, str] = {}
        self._importer_failures: dict[str, list[str]] = {}
        self._code_trees: dict[int, tuple[CodeType, ...]] = {}
        self._import_events: list[ImportEvidence] = []
        self._failed_imports: list[FailedImportEvidence] = []
        self._event_anchors: dict[int, tuple[object, ...]] = {}
        self._failed_event_anchors: dict[int, tuple[object, ...]] = {}
        self._import_hook: object | None = None
        self._import_module_hook: object | None = None
        if set(self._exports) - self._sources.keys():
            raise ValueError("capture_export_selection_invalid")
        for expected in self._sources.values():
            if (
                type(expected) is not ExpectedSource
                or type(expected.relative_path) is not str
                or type(expected.sha256) is not str
                or len(expected.sha256) != 64
                or any(char not in "0123456789abcdef" for char in expected.sha256)
            ):
                raise ValueError("capture_source_digest_invalid")
            relative = Path(expected.relative_path)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("capture_source_path_invalid")

    @property
    def failed(self) -> bool:
        """Whether this producer instance has reached its terminal failure."""

        return self._phase == "failed"

    @property
    def failure_reason(self) -> str | None:
        """Return the first producer failure without exposing exception objects."""

        return self._failure

    def diagnostic(self) -> SourceCaptureDiagnostic:
        """Describe collected evidence and its explicitly unresolved premises."""

        if not self._same_process():
            self._fail("capture_inherited_across_fork")
        rows: list[list[str]] = []
        for name, record in self._completed.items():
            if (
                type(name) is not str
                or type(record) is not ModuleExecution
                or type(record.relative_path) is not str
                or type(record.source_sha256) is not str
            ):
                self._fail("capture_record_invalid")
                rows = []
                break
            rows.append([name, record.relative_path, record.source_sha256])
        rows.sort(key=lambda row: row[0])
        source_digest = (
            hashlib.sha256(
                json.dumps(rows, ensure_ascii=True, separators=(",", ":")).encode("ascii")
            ).hexdigest()
            if rows
            else None
        )
        binding_failures = {
            "capture_finder_changed",
            "capture_path_finder_changed",
            "capture_finder_unqualified",
            "capture_finder_state_changed",
            "capture_process_owner_changed",
            "capture_import_hook_changed",
            "capture_loader_changed",
            "required_module_without_execution",
            "retained_module_changed",
            "retained_export_changed",
            "provider_export_not_recorded",
            "consumer_binding_changed",
            "capture_record_invalid",
            "importer_execution_not_recorded",
            "import_event_shape_unsupported",
            "import_event_package_unresolved",
            "import_event_provider_unresolved",
            "import_caller_code_unrecorded",
            "import_event_binding_unresolved",
            "import_event_binding_changed",
            "import_event_anchor_changed",
            "capture_inherited_across_fork",
        }
        failed_premise = (
            "complete_relevant_bindings"
            if self._failure in binding_failures
            else "appointed_profile"
            if self.failed
            and self._failure
            in {
                "selected_package_preloaded",
                "capture_preexisting_import_hooks_unsupported",
                "capture_installation_failed",
            }
            else "executed_bound_source"
            if self.failed
            else None
        )
        return SourceCaptureDiagnostic(
            schema_version="policyos.runtime.confidence_ledger.source_capture_diagnostic.v1",
            proof_schema="policyos.runtime.confidence_ledger.loaded_execution_capture.v1",
            identity_rule="canonical-source-execution/1",
            status="not_established",
            phase=self._phase,
            runtime_profile_id=None,
            first_unestablished_premise="appointed_profile",
            failed_premise=failed_premise,
            failure_code=self._failure,
            selected_source_count=len(self._sources),
            completed_module_count=len(self._completed),
            captured_source_projection_sha256=(
                f"sha256:{source_digest}" if source_digest is not None else None
            ),
            provider_projection_sha256=None,
            capture_time_role="in_progress_or_unavailable",
            currentness_time_role="not_evaluated",
            unresolved_by_construction=(
                "host_profile_appointment",
                "retained_producer_module_and_process_continuity",
                "selected_source_and_dependency_mapping",
                "relevant_graph_completeness",
                "unmediated_dynamic_code_and_uncaptured_importers",
                "direct_module_map_and_unmediated_provider_lookups",
                "owner_sealing_and_currentness",
                "material_decision_state",
                "protected_through_use",
            ),
        )

    def install(self) -> None:
        """Install the finder before a selected package has entered ``sys.modules``."""

        global _PROCESS_CAPTURE
        self._require_same_process()
        if self._phase != "new":
            raise CaptureError("capture_not_new")
        _imp.acquire_lock()
        try:
            if (
                _PROCESS_CAPTURE is not None
                or _passive_lookup(sys.__dict__, _PROCESS_OWNER_SLOT)[0]
            ):
                raise CaptureError("capture_process_already_attempted")
            # One owner for the process, including a failed first attempt. A
            # second recorder cannot retroactively adopt earlier initialization.
            _PROCESS_CAPTURE = self
            sys.__dict__[_PROCESS_OWNER_SLOT] = self
            try:
                if type(sys.modules) is not dict or any(
                    type(name) is str and name.partition(".")[0] in self._package_roots
                    for name in sys.modules
                ):
                    self._fail("selected_package_preloaded")
                    raise CaptureError("selected_package_preloaded")
                standard_meta = (
                    importlib.machinery.BuiltinImporter,
                    importlib.machinery.FrozenImporter,
                    importlib.machinery.PathFinder,
                )
                if len(sys.meta_path) != len(standard_meta) or any(
                    actual is not expected
                    for actual, expected in zip(sys.meta_path, standard_meta, strict=True)
                ):
                    self._fail("capture_preexisting_import_hooks_unsupported")
                    raise CaptureError("capture_preexisting_import_hooks_unsupported")
                self._initial_meta_path = tuple(sys.meta_path)
                sys.meta_path.insert(0, self._finder)
                if self._external_finder is not None:
                    if (
                        type.__getattribute__(_PATH_FINDER, "__dict__").get("find_spec")
                        is not _PATH_FINDER_DESCRIPTOR
                    ):
                        self._fail("capture_path_finder_changed")
                        raise CaptureError("capture_path_finder_changed")

                    def observed_path_find_spec(
                        cls: type[object],
                        fullname: str,
                        path: Sequence[str] | None = None,
                        target: ModuleType | None = None,
                    ) -> importlib.machinery.ModuleSpec | None:
                        if cls is _PATH_FINDER:
                            finder = self._external_finder
                            if finder is not None:
                                return finder.find_spec(fullname, path, target)
                        original_find_spec = cast(
                            "Callable[..., importlib.machinery.ModuleSpec | None]",
                            _PATH_FINDER_DESCRIPTOR.__func__,
                        )
                        return original_find_spec(cls, fullname, path, target)

                    self._path_finder_descriptor = classmethod(observed_path_find_spec)
                    type.__setattr__(_PATH_FINDER, "find_spec", self._path_finder_descriptor)
                self._meta_path_object = sys.meta_path
                self._admitted_meta_path = tuple(sys.meta_path)
                self._phase = "collecting"
                self._install_import_hooks()
            except BaseException:
                self._fail("capture_installation_failed")
                raise
        finally:
            _imp.release_lock()

    def completed(self, module_name: str) -> ModuleExecution:
        """Return a completed execution; a cyclic provisional module is refused."""

        self._require_same_process()
        if self._phase != "collecting":
            raise CaptureError("capture_not_collecting")
        try:
            return self._completed[module_name]
        except KeyError as exc:
            raise CaptureError("module_not_completed") from exc

    def assert_retained(self, required_modules: frozenset[str]) -> None:
        """Reconcile completed anchors for a nonempty, independently derived set.

        The caller must establish the required set separately. Success does not
        seal the capture or prove that every material edge has been selected.
        """

        self._require_same_process()
        if self._phase != "collecting":
            raise CaptureError("capture_incomplete")
        if (
            type(required_modules) is not frozenset
            or not required_modules
            or any(type(name) is not str for name in required_modules)
            or not required_modules.issubset(self._sources)
        ):
            raise CaptureError("capture_required_set_invalid")
        if any(name in self._pending for name in required_modules):
            raise CaptureError("capture_incomplete")
        if (
            sys.meta_path is not self._meta_path_object
            or len(sys.meta_path) != len(self._admitted_meta_path)
            or any(
                actual is not expected
                for actual, expected in zip(sys.meta_path, self._admitted_meta_path, strict=True)
            )
        ):
            self._fail("capture_finder_changed")
            raise CaptureError("capture_finder_changed")
        if self._path_finder_descriptor is not None and (
            type.__getattribute__(_PATH_FINDER, "__dict__").get("find_spec")
            is not self._path_finder_descriptor
        ):
            self._fail("capture_path_finder_changed")
            raise CaptureError("capture_path_finder_changed")
        if any(not self._source_finder_matches(ref) for ref in self._source_owned_finders.values()):
            self._fail("capture_finder_state_changed")
            raise CaptureError("capture_finder_state_changed")
        if _passive_lookup(sys.__dict__, _PROCESS_OWNER_SLOT)[1] is not self:
            self._fail("capture_process_owner_changed")
            raise CaptureError("capture_process_owner_changed")
        if (
            builtins.__import__ is not self._import_hook
            or importlib.import_module is not self._import_module_hook
        ):
            self._fail("capture_import_hook_changed")
            raise CaptureError("capture_import_hook_changed")
        if not _captured_loader_intact():
            self._fail("capture_loader_changed")
            raise CaptureError("capture_loader_changed")
        if required_modules.intersection(self._module_failures):
            self._fail("required_module_initialization_failed")
            raise CaptureError("required_module_initialization_failed")
        incomplete = required_modules.difference(self._completed)
        if any(_passive_lookup(sys.modules, name)[0] for name in incomplete):
            self._fail("required_module_without_execution")
            raise CaptureError("required_module_without_execution")
        if incomplete:
            raise CaptureError("capture_required_module_not_completed")
        for name in sorted(required_modules):
            record = self._completed[name]
            anchor = self._execution_anchors.get(name)
            if (
                type(record) is not ModuleExecution
                or anchor is None
                or anchor[0] is not record
                or any(
                    object.__getattribute__(record, field) is not original
                    for field, original in zip(_EXECUTION_FIELDS, anchor[1], strict=True)
                )
                or type(record.module) is not ModuleType
                or type(record.spec) is not importlib.machinery.ModuleSpec
                or type(record.loader) is not _CapturedSourceLoader
                or type(record.watched_exports) is not MappingProxyType
            ):
                self._fail("retained_module_changed")
                raise CaptureError("retained_module_changed")
            if not self._metadata_matches(
                name,
                record.module,
                record.loader,
                record.spec,
                record.origin,
                record.package,
                record.search_locations,
                record.package_search_locations,
                anchor[3],
                anchor[4],
            ):
                self._fail("retained_module_changed")
                raise CaptureError("retained_module_changed")
            original_exports = anchor[2]
            if any(
                type(export) is not str
                or (observed := _passive_lookup(record.watched_exports, export))[0] is False
                or observed[1] is not value
                for export, value in original_exports
            ) or len(record.watched_exports) != len(original_exports):
                self._fail("retained_export_changed")
                raise CaptureError("retained_export_changed")

    def completed_binding(self, module_name: str, name: str) -> object:
        """Reconcile a chosen actual post-initializer module binding by identity."""

        if type(module_name) is not str or type(name) is not str:
            raise CaptureError("captured_binding_invalid")
        self.assert_retained(frozenset({module_name}))
        record = self._completed[module_name]
        anchor = self._execution_anchors[module_name]
        original = next((value for key, value in anchor[2] if key == name), _MISSING)
        captured = _passive_lookup(record.watched_exports, name)
        current = _passive_lookup(record.module.__dict__, name)
        if original is _MISSING:
            self._fail("provider_export_not_recorded")
            raise CaptureError("provider_export_not_recorded")
        if (
            not captured[0]
            or captured[1] is not original
            or not current[0]
            or current[1] is not original
        ):
            self._fail("retained_export_changed")
            raise CaptureError("retained_export_changed")
        return original

    def assert_binding(
        self,
        importer_name: str,
        importer_attribute: str,
        provider_name: str,
        provider_attribute: str,
    ) -> None:
        """Compare a consumer's actual binding to a producer-time retained export."""

        if any(
            type(value) is not str
            for value in (importer_name, importer_attribute, provider_name, provider_attribute)
        ):
            raise CaptureError("consumer_binding_invalid")
        self.assert_retained(frozenset({importer_name, provider_name}))
        importer = self.completed(importer_name)
        retained = self.completed_binding(provider_name, provider_attribute)
        namespace = importer.module.__dict__
        found, observed = _passive_lookup(namespace, importer_attribute)
        if not found or observed is not retained:
            self._fail("consumer_binding_changed")
            raise CaptureError("consumer_binding_changed")

    def import_events(self) -> tuple[ImportEvidence, ...]:
        """Return collected import-site events without claiming their completeness."""

        self._require_same_process()
        if self._phase != "collecting":
            raise CaptureError("capture_not_collecting")
        return tuple(self._import_events)

    def relevant_graph(self, roots: frozenset[str]) -> RelevantGraphDiagnostic:
        """Project actual observed edges from owner-selected roots, without sealing.

        Import hooks do not capture arbitrary provider lookups or dynamic code;
        this graph is candidate evidence, not a complete readset or certificate.
        """

        self._require_same_process()
        if self._phase != "collecting":
            raise CaptureError("capture_not_collecting")
        if (
            type(roots) is not frozenset
            or not roots
            or any(type(name) is not str or name not in self._sources for name in roots)
        ):
            raise CaptureError("capture_graph_roots_invalid")
        events_by_importer: dict[str, list[ImportEvidence]] = {}
        failed_by_importer: dict[str, list[FailedImportEvidence]] = {}
        for event in self._import_events:
            self._check_import_event_anchor(event)
            events_by_importer.setdefault(event.importer_name, []).append(event)
        for event in self._failed_imports:
            self._check_failed_import_anchor(event)
            failed_by_importer.setdefault(event.importer_name, []).append(event)
        pending = list(roots)
        reached: set[str] = set()
        external: set[str] = set()
        failed: set[tuple[str, str | None]] = set()
        unresolved: set[tuple[str, str]] = set()
        while pending:
            name = pending.pop()
            if name in reached:
                continue
            reached.add(name)
            parent = name.rpartition(".")[0]
            if parent in self._sources:
                pending.append(parent)
            for reason in self._importer_failures.get(name, ()):
                unresolved.add((name, reason))
            for event in events_by_importer.get(name, ()):
                if event.unresolved_exports:
                    unresolved.add((name, "import_export_unresolved"))
                if event.provider_name in self._sources:
                    pending.append(event.provider_name)
                else:
                    external.add(event.provider_name)
                for value in event.retained_exports.values():
                    if type(value) is ModuleType:
                        found, exported_name = _passive_lookup(value.__dict__, "__name__")
                        if found and type(exported_name) is str and exported_name in self._sources:
                            pending.append(exported_name)
            for event in failed_by_importer.get(name, ()):
                failed.add((name, event.provider_name))
                if event.provider_name in self._sources:
                    pending.append(event.provider_name)
        return RelevantGraphDiagnostic(
            roots=tuple(sorted(roots)),
            reached_sources=tuple(sorted(reached)),
            external_providers=tuple(sorted(external)),
            failed_imports=tuple(sorted(failed, key=lambda row: (row[0], row[1] or ""))),
            failed_modules=tuple(
                sorted(
                    (name, reason)
                    for name, reason in self._module_failures.items()
                    if name in reached
                )
            ),
            unresolved_importers=tuple(sorted(unresolved)),
            pending_modules=tuple(sorted(reached.intersection(self._pending))),
        )

    def _check_import_event_anchor(self, event: ImportEvidence) -> None:
        anchor = self._event_anchors.get(id(event))
        if (
            type(event) is not ImportEvidence
            or anchor is None
            or anchor[0] is not event
            or any(
                object.__getattribute__(event, field) is not original
                for field, original in zip(_IMPORT_EVENT_FIELDS, anchor[1], strict=True)
            )
        ):
            self._fail("import_event_anchor_changed")
            raise CaptureError("import_event_anchor_changed")
        original_exports = anchor[2]
        if (
            type(event.retained_exports) is not MappingProxyType
            or len(event.retained_exports) != len(original_exports)
            or any(
                not (observed := _passive_lookup(event.retained_exports, name))[0]
                or observed[1] is not value
                for name, value in original_exports
            )
        ):
            self._fail("import_event_anchor_changed")
            raise CaptureError("import_event_anchor_changed")

    def _check_failed_import_anchor(self, event: FailedImportEvidence) -> None:
        anchor = self._failed_event_anchors.get(id(event))
        fields = ("importer_name", "importer", "caller_code", "provider_name", "route")
        if (
            type(event) is not FailedImportEvidence
            or anchor is None
            or anchor[0] is not event
            or any(
                object.__getattribute__(event, field) is not value
                for field, value in zip(fields, anchor[1], strict=True)
            )
        ):
            self._fail("import_event_anchor_changed")
            raise CaptureError("import_event_anchor_changed")

    def assert_import_binding(
        self,
        event: ImportEvidence,
        *,
        importer_attribute: str,
        provider_export: str,
    ) -> None:
        """Reconcile one observed provider value with its actual consumer binding.

        The owner must derive the import obligation independently and qualify
        external providers and material state; one matching event is not closure.
        """

        if (
            type(event) is not ImportEvidence
            or type(importer_attribute) is not str
            or type(provider_export) is not str
        ):
            raise CaptureError("import_event_not_recorded")
        anchor = self._event_anchors.get(id(event))
        if (
            anchor is None
            or anchor[0] is not event
            or any(
                object.__getattribute__(event, field) is not original
                for field, original in zip(_IMPORT_EVENT_FIELDS, anchor[1], strict=True)
            )
        ):
            self._fail("import_event_anchor_changed")
            raise CaptureError("import_event_anchor_changed")
        if (
            type(event.importer_name) is not str
            or type(event.provider_name) is not str
            or type(event.retained_exports) is not MappingProxyType
            or type(event.caller_code) is not CodeType
        ):
            self._fail("import_event_anchor_changed")
            raise CaptureError("import_event_anchor_changed")
        original_exports = anchor[2]
        if (
            type(original_exports) is not tuple
            or len(event.retained_exports) != len(original_exports)
            or any(
                type(name) is not str
                or not (observed := _passive_lookup(event.retained_exports, name))[0]
                or observed[1] is not value
                for name, value in original_exports
            )
        ):
            self._fail("import_event_anchor_changed")
            raise CaptureError("import_event_anchor_changed")
        required = {event.importer_name}
        if event.provider_name in self._sources:
            required.add(event.provider_name)
        self.assert_retained(frozenset(required))
        if event.provider_name in self._sources:
            self.completed_binding(event.provider_name, provider_export)
        if (
            type(event.importer) is not ModuleType
            or type(event.provider) is not ModuleType
            or _passive_lookup(sys.modules, event.importer_name)[1] is not event.importer
            or _passive_lookup(sys.modules, event.provider_name)[1] is not event.provider
        ):
            self._fail("import_event_binding_unresolved")
            raise CaptureError("import_event_binding_unresolved")
        found, retained = _passive_lookup(event.retained_exports, provider_export)
        if not found:
            self._fail("import_event_binding_unresolved")
            raise CaptureError("import_event_binding_unresolved")
        provider_namespace = event.provider.__dict__
        importer_namespace = event.importer.__dict__
        provider_found, current_provider = _passive_lookup(provider_namespace, provider_export)
        importer_found, current_importer = _passive_lookup(importer_namespace, importer_attribute)
        if (
            not provider_found
            or current_provider is not retained
            or not importer_found
            or current_importer is not retained
        ):
            self._fail("import_event_binding_changed")
            raise CaptureError("import_event_binding_changed")

    def _install_import_hooks(self) -> None:
        original_import = builtins.__import__
        original_import_module = importlib.import_module

        def observed_import(
            name: str,
            globals: dict[str, object] | None = None,
            locals: dict[str, object] | None = None,
            fromlist: tuple[str, ...] | list[str] | None = (),
            level: int = 0,
        ) -> ModuleType:
            caller = sys._getframe(1)
            if self._phase == "collecting":
                with suppress(CaptureError):
                    self._refresh_meta_path()
            try:
                result = original_import(name, globals, locals, fromlist, level)
            except BaseException:
                if self._phase == "collecting":
                    provider_name = self._absolute_import_name(caller, name, level)
                    self._record_failed_import(caller, provider_name, "builtin_import")
                raise
            if self._phase == "collecting" and not self._same_process():
                self._fail("capture_inherited_across_fork")
            if self._phase == "collecting":
                self._record_import(caller, name, fromlist, level, result, "builtin_import")
            return result

        def observed_import_module(name: str, package: str | None = None) -> ModuleType:
            caller = sys._getframe(1)
            if self._phase == "collecting":
                with suppress(CaptureError):
                    self._refresh_meta_path()
            try:
                result = original_import_module(name, package)
            except BaseException:
                if self._phase == "collecting":
                    provider_name: str | None = None
                    if type(name) is str and not name.startswith("."):
                        provider_name = name
                    elif type(name) is str and type(package) is str:
                        with suppress(ImportError, ValueError):
                            provider_name = importlib.util.resolve_name(name, package)
                    self._record_failed_import(caller, provider_name, "import_module")
                raise
            if self._phase == "collecting" and not self._same_process():
                self._fail("capture_inherited_across_fork")
            if self._phase == "collecting":
                self._record_import_module(caller, result)
            return result

        self._import_hook = observed_import
        self._import_module_hook = observed_import_module
        builtins.__import__ = observed_import
        importlib.import_module = observed_import_module

    def _source_finder_reference(self, finder: object) -> _SourceOwnedFinder | None:
        """Retain the source-executed resolution path of the actual finder."""

        finder_type = type(finder)
        mro = type.__getattribute__(finder_type, "__mro__")
        if type(mro) is not tuple:
            return None
        dictionary_descriptor = next(
            (
                _passive_lookup(type.__getattribute__(cls, "__dict__"), "__dict__")[1]
                for cls in mro
                if _passive_lookup(type.__getattribute__(cls, "__dict__"), "__dict__")[0]
            ),
            None,
        )
        if type(dictionary_descriptor) is not GetSetDescriptorType:
            return None
        namespace = object.__getattribute__(finder, "__dict__")
        if type(namespace) is not dict or any(type(key) is not str for key in namespace):
            return None
        instance_fields = tuple(namespace.items())
        classes: list[_SourceFinderClass] = []
        for cls in mro:
            owner_name = type.__getattribute__(cls, "__module__")
            class_name = type.__getattribute__(cls, "__name__")
            fields = type.__getattribute__(cls, "__dict__")
            bases = type.__getattribute__(cls, "__bases__")
            if (
                type(owner_name) is not str
                or type(class_name) is not str
                or type(bases) is not tuple
                or owner_name not in self._sources
            ):
                return None
            owner = self._pending.get(owner_name)
            code = self._pending_codes.get(owner_name)
            if owner is None:
                completed = self._completed.get(owner_name)
                if completed is None:
                    return None
                owner, code = completed.module, completed.code
            if (
                type(owner) is not ModuleType
                or type(code) is not CodeType
                or _passive_lookup(sys.modules, owner_name)[1] is not owner
                or _passive_lookup(owner.__dict__, class_name)[1] is not cls
            ):
                return None
            functions: list[tuple[object, ...]] = []
            for value in fields.values():
                accessors = _finder_descriptor_functions(value)
                if accessors is None:
                    continue
                for function in accessors:
                    if (
                        type(function) is not FunctionType
                        or function.__globals__ is not owner.__dict__
                        or not self._code_belongs_to(code, function.__code__)
                    ):
                        return None
                    held = _finder_callable_hold(function)
                    if held is None:
                        return None
                    functions.append(held)
            classes.append(
                _SourceFinderClass(
                    cls,
                    owner,
                    owner_name,
                    class_name,
                    code,
                    bases,
                    tuple(fields.items()),
                    tuple(functions),
                )
            )
            found, descriptor = _passive_lookup(fields, "find_spec")
            if not found:
                continue
            if type(descriptor) not in (FunctionType, classmethod, staticmethod):
                return None
            accessors = _finder_descriptor_functions(descriptor)
            if accessors is None or len(accessors) != 1:
                return None
            method = accessors[0]
            if (
                type(method) is not FunctionType
                or method.__globals__ is not owner.__dict__
                or not self._code_belongs_to(code, method.__code__)
            ):
                return None
            return _SourceOwnedFinder(
                finder,
                finder_type,
                mro,
                tuple(classes),
                method,
                method.__code__,
                namespace,
                instance_fields,
            )
        return None

    def _source_finder_matches(self, reference: _SourceOwnedFinder) -> bool:
        if type(reference.finder) is not reference.finder_type:
            return False
        mro = type.__getattribute__(reference.finder_type, "__mro__")
        if (
            type(mro) is not tuple
            or len(mro) != len(reference.resolution_order)
            or any(
                actual is not held
                for actual, held in zip(mro, reference.resolution_order, strict=True)
            )
            or reference.method.__code__ is not reference.method_code
        ):
            return False
        for item in reference.classes:
            fields = type.__getattribute__(item.cls, "__dict__")
            bases = type.__getattribute__(item.cls, "__bases__")
            owner = self._pending.get(item.owner_name)
            code = self._pending_codes.get(item.owner_name)
            if owner is None:
                completed = self._completed.get(item.owner_name)
                if completed is None:
                    return False
                owner, code = completed.module, completed.code
            if (
                type(bases) is not tuple
                or len(bases) != len(item.bases)
                or any(actual is not held for actual, held in zip(bases, item.bases, strict=True))
                or owner is not item.owner
                or code is not item.source_code
                or _passive_lookup(sys.modules, item.owner_name)[1] is not item.owner
                or _passive_lookup(item.owner.__dict__, item.class_name)[1] is not item.cls
                or len(fields) != len(item.fields)
                or any(
                    not _passive_binding_matches(fields, name, value) for name, value in item.fields
                )
                or not all(_finder_callable_unchanged(held) for held in item.functions)
            ):
                return False
        namespace = object.__getattribute__(reference.finder, "__dict__")
        return bool(
            namespace is reference.instance_namespace
            and len(namespace) == len(reference.instance_fields)
            and all(
                _passive_binding_matches(namespace, name, value)
                for name, value in reference.instance_fields
            )
        )

    def _refresh_meta_path(self) -> None:
        """Keep the recorder first and retain newly observed source-owned finders.

        This records construction and identity only. A later authority owner must
        still qualify each finder's decision state and any external providers.
        """

        if sys.meta_path is not self._meta_path_object or type(sys.meta_path) is not list:
            self._fail("capture_finder_changed")
            raise CaptureError("capture_finder_changed")
        current = tuple(sys.meta_path)
        if sum(finder is self._finder for finder in current) != 1:
            self._fail("capture_finder_changed")
            raise CaptureError("capture_finder_changed")
        if self._path_finder_descriptor is not None and (
            type.__getattribute__(_PATH_FINDER, "__dict__").get("find_spec")
            is not self._path_finder_descriptor
        ):
            self._fail("capture_path_finder_changed")
            raise CaptureError("capture_path_finder_changed")
        baseline = tuple(
            finder
            for finder in current
            if any(finder is original for original in self._initial_meta_path)
        )
        if len(baseline) != len(self._initial_meta_path) or any(
            actual is not original
            for actual, original in zip(baseline, self._initial_meta_path, strict=True)
        ):
            self._fail("capture_finder_changed")
            raise CaptureError("capture_finder_changed")
        for finder in current:
            if finder is self._finder or any(
                finder is original for original in self._initial_meta_path
            ):
                continue
            reference = self._source_owned_finders.get(id(finder))
            if reference is None:
                reference = self._source_finder_reference(finder)
                if reference is None:
                    self._fail("capture_finder_unqualified")
                    raise CaptureError("capture_finder_unqualified")
                self._source_owned_finders[id(finder)] = reference
            if reference.finder is not finder or not self._source_finder_matches(reference):
                self._fail("capture_finder_state_changed")
                raise CaptureError("capture_finder_state_changed")
        if any(
            sum(finder is reference.finder for finder in current) != 1
            for reference in self._source_owned_finders.values()
        ):
            self._fail("capture_finder_changed")
            raise CaptureError("capture_finder_changed")
        if current[0] is not self._finder:
            sys.meta_path[:] = [
                self._finder,
                *(finder for finder in current if finder is not self._finder),
            ]
        self._admitted_meta_path = tuple(sys.meta_path)

    def _selected_importer(self, caller: FrameType) -> tuple[str, ModuleType] | None:
        namespace = caller.f_globals
        _, name = _passive_lookup(namespace, "__name__")
        if type(name) is not str or name not in self._sources:
            return None
        importer = self._pending.get(name)
        if importer is None:
            completed = self._completed.get(name)
            importer = completed.module if completed is not None else None
        if type(importer) is not ModuleType or importer.__dict__ is not namespace:
            self._importer_fail(name, "importer_execution_not_recorded")
            return None
        root_code = (
            self._pending_codes.get(name) if name in self._pending else self._completed[name].code
        )
        if root_code is None or not self._code_belongs_to(root_code, caller.f_code):
            self._importer_fail(name, "import_caller_code_unrecorded")
            return None
        return name, importer

    def _code_belongs_to(self, root: CodeType, selected: CodeType) -> bool:
        """Compare actual code identities within the retained compiler tree."""

        key = id(root)
        tree = self._code_trees.get(key)
        if tree is None or tree[0] is not root:
            pending = [root]
            members: list[CodeType] = []
            while pending:
                code = pending.pop()
                members.append(code)
                pending.extend(item for item in code.co_consts if type(item) is CodeType)
            tree = tuple(members)
            self._code_trees[key] = tree
        return any(code is selected for code in tree)

    def _record_import(
        self,
        caller: FrameType,
        requested: str,
        fromlist: tuple[str, ...] | list[str] | None,
        level: int,
        returned: object,
        route: Literal["builtin_import"],
    ) -> None:
        selected = self._selected_importer(caller)
        if selected is None:
            return
        if (
            type(requested) is not str
            or type(level) is not int
            or level < 0
            or (fromlist is not None and type(fromlist) not in (tuple, list))
            or (fromlist is not None and any(type(name) is not str for name in fromlist))
            or type(returned) is not ModuleType
        ):
            self._importer_fail(selected[0], "import_event_shape_unsupported")
            return
        provider_name = self._absolute_import_name(caller, requested, level)
        if provider_name is None:
            self._importer_fail(selected[0], "import_event_package_unresolved")
            return
        _, provider = _passive_lookup(sys.modules, provider_name)
        if type(provider) is not ModuleType:
            self._importer_fail(selected[0], "import_event_provider_unresolved")
            return
        self._retain_import_event(
            selected,
            caller.f_code,
            caller.f_lineno,
            provider_name,
            provider,
            returned,
            tuple(fromlist or ()),
            route,
        )

    def _record_import_module(self, caller: FrameType, returned: object) -> None:
        selected = self._selected_importer(caller)
        if selected is None:
            return
        if type(returned) is not ModuleType:
            self._importer_fail(selected[0], "import_event_provider_unresolved")
            return
        _, provider_name = _passive_lookup(returned.__dict__, "__name__")
        if (
            type(provider_name) is not str
            or _passive_lookup(sys.modules, provider_name)[1] is not returned
        ):
            self._importer_fail(selected[0], "import_event_provider_unresolved")
            return
        self._retain_import_event(
            selected,
            caller.f_code,
            caller.f_lineno,
            provider_name,
            returned,
            returned,
            (),
            "import_module",
        )

    def _absolute_import_name(
        self, caller: FrameType, requested: object, level: object
    ) -> str | None:
        if type(requested) is not str or type(level) is not int or level < 0:
            return None
        if not level:
            return requested or None
        _, package = _passive_lookup(caller.f_globals, "__package__")
        if type(package) is not str or not package or level > len(package.split(".")):
            return None
        parent = package.rsplit(".", level - 1)[0]
        return f"{parent}.{requested}" if requested else parent

    def _record_failed_import(
        self,
        caller: FrameType,
        provider_name: str | None,
        route: Literal["builtin_import", "import_module"],
    ) -> None:
        selected = self._selected_importer(caller)
        if selected is None:
            return
        event = FailedImportEvidence(selected[0], selected[1], caller.f_code, provider_name, route)
        fields = (
            event.importer_name,
            event.importer,
            event.caller_code,
            event.provider_name,
            event.route,
        )
        self._failed_event_anchors[id(event)] = (event, fields)
        self._failed_imports.append(event)

    def _retain_import_event(
        self,
        selected: tuple[str, ModuleType],
        caller_code: CodeType,
        caller_line: int,
        provider_name: str,
        provider: ModuleType,
        returned: ModuleType,
        exports: tuple[str, ...],
        route: Literal["builtin_import", "import_module"],
    ) -> None:
        namespace = provider.__dict__
        selected_exports: dict[str, object] = {}
        unresolved_names: list[str] = []
        for name in exports:
            found, value = _passive_lookup(namespace, name)
            if name == "*" or not found:
                unresolved_names.append(name)
            else:
                selected_exports[name] = value
        retained = MappingProxyType(selected_exports)
        unresolved = tuple(unresolved_names)
        event = ImportEvidence(
            selected[0],
            selected[1],
            caller_code,
            caller_line,
            provider_name,
            provider,
            returned,
            exports,
            retained,
            unresolved,
            route,
        )
        fields = tuple(object.__getattribute__(event, field) for field in _IMPORT_EVENT_FIELDS)
        self._event_anchors[id(event)] = (event, fields, tuple(selected_exports.items()))
        self._import_events.append(event)

    def _selected_path(self, expected: ExpectedSource) -> Path:
        relative = Path(expected.relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("capture_source_path_invalid")
        selected = self._root / relative
        if (
            selected.resolve(strict=True) != selected
            or not selected.is_relative_to(self._root)
            or not selected.is_file()
        ):
            raise ValueError("capture_source_path_invalid")
        return selected

    def _begin(self, name: str, module: ModuleType, loader: _CapturedSourceLoader) -> None:
        if (
            self._phase != "collecting"
            or name in self._pending
            or name in self._completed
            or type(module) is not ModuleType
            or _passive_lookup(sys.modules, name)[1] is not module
            or _passive_lookup(module.__dict__, "__loader__")[1] is not loader
        ):
            self._module_fail(name, "module_initialization_invalid")
            raise CaptureError("module_initialization_invalid")
        self._pending[name] = module

    def _bind_initialization_code(self, name: str, module: ModuleType, code: CodeType) -> None:
        if (
            self._phase != "collecting"
            or self._pending.get(name) is not module
            or name in self._pending_codes
            or type(code) is not CodeType
        ):
            raise CaptureError("module_initialization_invalid")
        self._pending_codes[name] = code

    def _complete(
        self,
        name: str,
        module: ModuleType,
        loader: _CapturedSourceLoader,
        source_sha256: str,
        code: CodeType,
    ) -> None:
        if (
            self._phase != "collecting"
            or self._pending.get(name) is not module
            or self._pending_codes.get(name) is not code
        ):
            raise CaptureError("module_initialization_invalid")
        namespace = module.__dict__
        _, spec = _passive_lookup(namespace, "__spec__")
        if type(spec) is not importlib.machinery.ModuleSpec:
            raise CaptureError("module_initialization_invalid")
        spec_fields = object.__getattribute__(spec, "__dict__")
        locations = _passive_lookup(spec_fields, "submodule_search_locations")[1]
        if locations is not None and (
            type(locations) is not list or any(type(item) is not str for item in locations)
        ):
            raise CaptureError("module_initialization_invalid")
        search_locations = None if locations is None else tuple(locations)
        package_path = _passive_lookup(namespace, "__path__")[1]
        if locations is None:
            package_search_locations = None
        elif type(package_path) is not list or any(type(item) is not str for item in package_path):
            raise CaptureError("module_initialization_invalid")
        else:
            package_search_locations = tuple(package_path)
        package = name if search_locations is not None else name.rpartition(".")[0]
        selected_origin = str(self._selected_path(self._sources[name]))
        if not self._metadata_matches(
            name,
            module,
            loader,
            spec,
            selected_origin,
            package,
            search_locations,
            package_search_locations,
            locations,
            package_path,
        ):
            raise CaptureError("module_initialization_invalid")
        names = self._exports.get(name, frozenset())
        values: dict[str, object] = {}
        for export in names:
            found, value = _passive_lookup(namespace, export)
            # A source-derived candidate can be absent in the selected branch.
            # The owner must refuse if an actual required binding is absent.
            if found:
                values[export] = value
        retained = MappingProxyType(values)
        record = ModuleExecution(
            name,
            self._sources[name].relative_path,
            source_sha256,
            code,
            module,
            loader,
            spec,
            selected_origin,
            package,
            search_locations,
            package_search_locations,
            retained,
        )
        fields = tuple(object.__getattribute__(record, field) for field in _EXECUTION_FIELDS)
        self._execution_anchors[name] = (
            record,
            fields,
            tuple(values.items()),
            locations,
            package_path,
        )
        self._completed[name] = record
        del self._pending[name]
        del self._pending_codes[name]
        self._refresh_meta_path()

    def _metadata_matches(
        self,
        name: str,
        module: ModuleType,
        loader: _CapturedSourceLoader,
        spec: importlib.machinery.ModuleSpec,
        origin: str,
        package: str,
        search_locations: tuple[str, ...] | None,
        package_search_locations: tuple[str, ...] | None,
        original_spec_locations: object,
        original_package_path: object,
    ) -> bool:
        """Inspect exact builtin representations without candidate comparisons."""

        if (
            type(module) is not ModuleType
            or type(spec) is not importlib.machinery.ModuleSpec
            or type(loader) is not _CapturedSourceLoader
        ):
            return False
        namespace = module.__dict__
        spec_fields = object.__getattribute__(spec, "__dict__")
        loader_fields = object.__getattribute__(loader, "__dict__")
        fields = (
            (_passive_lookup(namespace, "__name__")[1], name),
            (_passive_lookup(namespace, "__package__")[1], package),
            (_passive_lookup(namespace, "__file__")[1], origin),
            (_passive_lookup(spec_fields, "name")[1], name),
            (_passive_lookup(spec_fields, "origin")[1], origin),
            (_passive_lookup(loader_fields, "name")[1], name),
            (_passive_lookup(loader_fields, "path")[1], origin),
        )
        if any(type(value) is not str or value != expected for value, expected in fields):
            return False
        if (
            _passive_lookup(sys.modules, name)[1] is not module
            or _passive_lookup(namespace, "__loader__")[1] is not loader
            or _passive_lookup(namespace, "__spec__")[1] is not spec
            or _passive_lookup(spec_fields, "loader")[1] is not loader
            or _passive_lookup(loader_fields, "_capture")[1] is not self
            or _passive_lookup(loader_fields, "_expected")[1] is not self._sources[name]
        ):
            return False
        locations = _passive_lookup(spec_fields, "submodule_search_locations")[1]
        if search_locations is None:
            return locations is None and not _passive_lookup(namespace, "__path__")[0]
        package_path = _passive_lookup(namespace, "__path__")[1]
        return (
            type(locations) is list
            and locations is original_spec_locations
            and all(type(item) is str for item in locations)
            and tuple(locations) == search_locations
            and type(package_path) is list
            and package_path is original_package_path
            and all(type(item) is str for item in package_path)
            and tuple(package_path) == package_search_locations
        )

    def _fail(self, reason: str) -> None:
        self._phase = "failed"
        if self._failure is None:
            self._failure = reason

    def _module_fail(self, name: str, reason: str) -> None:
        self._module_failures.setdefault(name, reason)
        self._pending.pop(name, None)
        self._pending_codes.pop(name, None)

    def _importer_fail(self, name: str, reason: str) -> None:
        self._importer_failures.setdefault(name, []).append(reason)

    def _same_process(self) -> bool:
        return _GETPID() == self._process_id

    def _require_same_process(self) -> None:
        if not self._same_process():
            self._fail("capture_inherited_across_fork")
            raise CaptureError("capture_inherited_across_fork")
