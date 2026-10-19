"""Focused architecture report validator owner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tools.quality.validation.architecture_package_contracts import (
    _MISSING_VALUE,
    PACKAGE_MIRROR_CHECK_COMMAND,
    PACKAGE_MIRROR_FAMILY_ID,
    PACKAGE_MIRROR_OUTPUTS,
    PACKAGE_MIRROR_SOURCE_OF_TRUTH,
)

if TYPE_CHECKING:
    from tools.quality.validation.architecture_package_contracts import (
        ArchitectureReportServices,
        FindingLike,
        _PackageMirrorFamilyAdmission,
    )

import tomllib
from pathlib import Path, PurePosixPath
from typing import Any


def _validate_package_mirror_projection(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
    _services: ArchitectureReportServices,
) -> tuple[list[FindingLike], dict[str, Any]]:
    admission = family_admission or _services.dispatch(
        "_admit_package_mirror_family_registry", repo_root
    )
    errors = _services.dispatch("_family_registry_findings", admission, check="package-mirror")
    family_path = "architecture/generated_artifacts.toml"
    family_matches = [
        family_row
        for family_row in admission.rows
        if family_row.get("id") == PACKAGE_MIRROR_FAMILY_ID
    ]
    family = family_matches[0] if len(family_matches) == 1 else {}
    if len(family_matches) != 1:
        errors.append(
            _services.finding(
                "package-mirror",
                "error",
                family_path,
                "package-mirror family must be registered exactly once",
                f"matches={len(family_matches)}",
            )
        )
    raw_outputs = family.get("outputs", _MISSING_VALUE)
    outputs = (
        [value for value in raw_outputs if type(value) is str] if type(raw_outputs) is list else []
    )
    output_set = set(outputs)
    expected_outputs = set(PACKAGE_MIRROR_OUTPUTS.values())
    if type(raw_outputs) is not list or len(outputs) != len(raw_outputs):
        errors.append(
            _services.finding(
                "package-mirror",
                "error",
                family_path,
                "package-mirror outputs must be a list of repository-relative paths",
            )
        )
    if len(outputs) != len(output_set):
        errors.append(
            _services.finding(
                "package-mirror",
                "error",
                family_path,
                "package-mirror outputs contain duplicate paths",
            )
        )
    if output_set != expected_outputs:
        errors.append(
            _services.finding(
                "package-mirror",
                "error",
                family_path,
                "registered outputs differ from the package projection schema",
                f"missing={sorted(expected_outputs - output_set)!r} "
                f"extra={sorted(output_set - expected_outputs)!r}",
            )
        )
    for output in outputs:
        path = PurePosixPath(output)
        if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
            errors.append(
                _services.finding(
                    "package-mirror",
                    "error",
                    family_path,
                    "output path is not repository-relative and traversal-free",
                    output,
                )
            )
    source_basis = family.get("source_of_truth", _MISSING_VALUE)
    if type(source_basis) is not str or source_basis != PACKAGE_MIRROR_SOURCE_OF_TRUTH:
        errors.append(
            _services.finding(
                "package-mirror",
                "error",
                family_path,
                "source basis must exclude registered family outputs",
                f"type={_services.dispatch('_mirror_value_type', source_basis)} value={source_basis!r}",
            )
        )
    command = family.get("check_command", _MISSING_VALUE)
    if type(command) is not list or command != list(PACKAGE_MIRROR_CHECK_COMMAND):
        errors.append(
            _services.finding(
                "package-mirror",
                "error",
                family_path,
                "family check_command must match the canonical verifier route",
                f"expected={list(PACKAGE_MIRROR_CHECK_COMMAND)!r} observed={command!r}",
            )
        )

    source_contracts = _services.dispatch(
        "_load_package_contracts", repo_root, family_admission=admission
    )
    primary = [
        (p, d)
        for p, d in source_contracts
        if isinstance(d.get("package"), dict) and d["package"].get("primary_contract") is True
    ]
    by_module: dict[str, tuple[Path, dict[str, Any]]] = {}
    by_name: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path, data in primary:
        package = data["package"]
        raw_module = package.get("module", _MISSING_VALUE)
        raw_name = package.get("name", _MISSING_VALUE)
        subject = _services.dispatch("_relative", path, repo_root)
        identity_is_valid = True
        for field, value in (("package.module", raw_module), ("package.name", raw_name)):
            if type(value) is not str or not value.strip() or value != value.strip():
                errors.append(
                    _services.finding(
                        "package-mirror",
                        "error",
                        subject,
                        f"{field} has malformed source value",
                        f"expected non-empty trimmed string; got {_services.dispatch('_mirror_value_type', value)}",
                    )
                )
                identity_is_valid = False
        if not identity_is_valid:
            continue
        module, name = raw_module, raw_name
        if module in by_module:
            errors.append(
                _services.finding(
                    "package-mirror",
                    "error",
                    subject,
                    "primary contracts duplicate package.module",
                    module,
                )
            )
        else:
            by_module[module] = (path, data)
        if name in by_name:
            errors.append(
                _services.finding(
                    "package-mirror",
                    "error",
                    subject,
                    "primary contracts duplicate package.name",
                    name,
                )
            )
        else:
            by_name[name] = (path, data)
    if not primary:
        errors.append(
            _services.finding(
                "package-mirror",
                "error",
                "architecture/packages",
                "no primary package source contracts were discovered",
            )
        )

    def projection(relative: str) -> dict[str, Any]:
        try:
            return _services.read_toml(repo_root / relative)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(
                _services.finding(
                    "package-mirror",
                    "error",
                    relative,
                    "package projection is missing or malformed",
                    str(exc),
                )
            )
            return {}

    def rows_index(rows: object, identity: str, subject: str) -> dict[str, dict[str, Any]]:
        if not isinstance(rows, list):
            errors.append(
                _services.finding(
                    "package-mirror", "error", subject, "projection rows must be an array"
                )
            )
            return {}
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                errors.append(
                    _services.finding(
                        "package-mirror", "error", subject, "projection row must be a table"
                    )
                )
                continue
            raw_key = row.get(identity, _MISSING_VALUE)
            if type(raw_key) is not str:
                errors.append(
                    _services.finding(
                        "package-mirror",
                        "error",
                        subject,
                        f"projection row `{identity}` has malformed identity value",
                        f"expected string; got {_services.dispatch('_mirror_value_type', raw_key)}",
                    )
                )
                continue
            key = raw_key
            if not key.strip() or key != key.strip():
                errors.append(
                    _services.finding(
                        "package-mirror", "error", subject, f"projection row lacks `{identity}`"
                    )
                )
            elif key in result:
                errors.append(
                    _services.finding(
                        "package-mirror",
                        "error",
                        subject,
                        f"projection rows duplicate `{identity}`",
                        key,
                    )
                )
            else:
                result[key] = row
        return result

    def source_table(data: dict[str, Any], table: str, subject: str) -> dict[str, Any]:
        value = data.get(table, _MISSING_VALUE)
        if type(value) is dict:
            return value
        _services.dispatch(
            "_record_malformed_mirror_value",
            errors,
            subject,
            table,
            value,
            domain="table",
            side="source",
        )
        return {}

    def check_set(label: str, expected: set[str], observed: set[str], subject: str) -> None:
        for item in sorted(expected - observed):
            errors.append(
                _services.finding(
                    "package-mirror",
                    "error",
                    subject,
                    f"{label} is missing a source-derived row",
                    item,
                )
            )
        for item in sorted(observed - expected):
            errors.append(
                _services.finding(
                    "package-mirror",
                    "error",
                    label,
                    "projection row has no matching source declaration",
                    item,
                )
            )

    expected_modules = set(by_module)
    boundary_path = PACKAGE_MIRROR_OUTPUTS["boundaries"]
    boundaries = rows_index(projection(boundary_path).get("package"), "module", boundary_path)
    check_set("package boundaries", expected_modules, set(boundaries), boundary_path)
    for module, (path, data) in by_module.items():
        row = boundaries.get(module)
        if row is None:
            continue
        subject = _services.dispatch("_relative", path, repo_root)
        package = source_table(data, "package", subject)
        source = source_table(data, "boundaries", subject)
        for field, expected in (
            ("owner", package.get("owner", _MISSING_VALUE)),
            ("public_facade", source.get("public_facade", _MISSING_VALUE)),
        ):
            _services.dispatch(
                "_compare_scalar",
                errors,
                subject,
                f"package_boundaries.{field}",
                expected=expected,
                observed=row.get(field, _MISSING_VALUE),
            )
        for field in ("allowed_dependencies", "forbidden_dependencies"):
            _services.dispatch(
                "_compare_list",
                errors,
                subject,
                f"package_boundaries.{field}",
                expected=source.get(field, _MISSING_VALUE),
                observed=row.get(field, _MISSING_VALUE),
            )
        for field in ("compatibility_shim", "shim_id"):
            _services.dispatch(
                "_compare_optional_scalar",
                errors,
                subject,
                f"package_boundaries.{field}",
                expected=source.get(field),
                observed=row.get(field),
            )
        _services.dispatch(
            "_compare_optional_list",
            errors,
            subject,
            "package_boundaries.runtime_allowed_submodules",
            expected=source.get("runtime_allowed_submodules"),
            observed=row.get("runtime_allowed_submodules"),
        )

    public_path = PACKAGE_MIRROR_OUTPUTS["public_surface"]
    public_rows = rows_index(projection(public_path).get("package"), "module", public_path)
    public_sources: dict[str, tuple[Path, dict[str, Any]]] = {}
    declared_entrypoints: set[str] = set()
    for source_path, source_data in source_contracts:
        source_subject = _services.dispatch("_relative", source_path, repo_root)
        source_package = source_table(source_data, "package", source_subject)
        source_surface = source_table(source_data, "public_surface", source_subject)
        source_module = source_package.get("module", _MISSING_VALUE)
        if (
            type(source_module) is not str
            or not source_module.strip()
            or source_module != source_module.strip()
        ):
            continue
        if source_module in public_sources:
            errors.append(
                _services.finding(
                    "package-mirror",
                    "error",
                    _services.dispatch("_relative", source_path, repo_root),
                    "public surface source contracts duplicate package.module",
                    source_module,
                )
            )
            continue
        public_sources[source_module] = (source_path, source_data)
        raw_entrypoints = source_surface.get("supported_entrypoints", _MISSING_VALUE)
        if type(raw_entrypoints) is list:
            declared_entrypoints.update(
                entry for entry in raw_entrypoints if type(entry) is str and entry
            )

    public_source_modules = set(public_sources)
    check_set(
        "public surface",
        public_source_modules,
        public_source_modules & set(public_rows),
        public_path,
    )
    unmapped_public_surface_rows: dict[str, dict[str, Any]] = {}
    for extra in sorted(set(public_rows) - public_source_modules):
        row = public_rows[extra]
        unverified_fields = sorted(field for field in row if field != "module")
        parent_entrypoint_declared = extra in declared_entrypoints
        unmapped_public_surface_rows[extra] = {
            "status": "not_established",
            "parent_entrypoint_declared": parent_entrypoint_declared,
            "unverified_fields": unverified_fields,
        }
        errors.append(
            _services.finding(
                "package-mirror",
                "error",
                public_path,
                "public surface row has no complete source contract",
                f"module={extra!r} status=not_established "
                f"parent_entrypoint_declared={parent_entrypoint_declared} "
                f"unverified_fields={unverified_fields!r}",
            )
        )

    for module, (path, data) in public_sources.items():
        row = public_rows.get(module)
        if row is None:
            continue
        surface = source_table(
            data, "public_surface", _services.dispatch("_relative", path, repo_root)
        )
        layout = source_table(data, "layout", _services.dispatch("_relative", path, repo_root))
        source_values = (
            ("classification", surface.get("classification", _MISSING_VALUE)),
            ("facade_mode", surface.get("facade_mode", _MISSING_VALUE)),
            ("owner", surface.get("registry_owner", _MISSING_VALUE)),
            ("readme", layout.get("readme", _MISSING_VALUE)),
            ("reference_doc", surface.get("reference_doc", _MISSING_VALUE)),
            ("notes", surface.get("notes", _MISSING_VALUE)),
        )
        for field, expected in source_values:
            _services.dispatch(
                "_compare_scalar",
                errors,
                _services.dispatch("_relative", path, repo_root),
                f"public_surface.{field}",
                expected=expected,
                observed=row.get(field, _MISSING_VALUE),
            )
        _services.dispatch(
            "_compare_boolean",
            errors,
            _services.dispatch("_relative", path, repo_root),
            "public_surface.major_subsystem",
            expected=surface.get("major_subsystem", _MISSING_VALUE),
            observed=row.get("major_subsystem", _MISSING_VALUE),
        )
        _services.dispatch(
            "_compare_list",
            errors,
            _services.dispatch("_relative", path, repo_root),
            "public_surface.supported_entrypoints",
            expected=surface.get("supported_entrypoints", _MISSING_VALUE),
            observed=row.get("supported_entrypoints", _MISSING_VALUE),
        )

    layout_path = PACKAGE_MIRROR_OUTPUTS["layout"]
    layout_rows = rows_index(projection(layout_path).get("package"), "name", layout_path)
    expected_layout: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path, data in primary:
        layout = source_table(data, "layout", _services.dispatch("_relative", path, repo_root))
        mirror_value = layout.get("legacy_layout_mirror", _MISSING_VALUE)
        if type(mirror_value) is not str:
            _services.dispatch(
                "_record_malformed_mirror_value",
                errors,
                _services.dispatch("_relative", path, repo_root),
                "layout.legacy_layout_mirror",
                mirror_value,
                domain="string",
                side="source",
            )
            continue
        mirror = mirror_value
        if mirror != mirror.strip():
            errors.append(
                _services.finding(
                    "package-mirror",
                    "error",
                    _services.dispatch("_relative", path, repo_root),
                    "layout.legacy_layout_mirror has malformed source value",
                    "expected an exact unpadded repository-relative path",
                )
            )
        if mirror and mirror not in output_set:
            errors.append(
                _services.finding(
                    "package-mirror",
                    "error",
                    _services.dispatch("_relative", path, repo_root),
                    "layout mirror path is not registered by its generated family",
                    mirror,
                )
            )
        if mirror == layout_path:
            package = source_table(
                data, "package", _services.dispatch("_relative", path, repo_root)
            )
            name = package.get("name", _MISSING_VALUE)
            if type(name) is str and name.strip() and name == name.strip():
                expected_layout[name] = (path, data)
            else:
                _services.dispatch(
                    "_record_malformed_mirror_value",
                    errors,
                    _services.dispatch("_relative", path, repo_root),
                    "package.name",
                    name,
                    domain="string",
                    side="source",
                )
    check_set("package layout", set(expected_layout), set(layout_rows), layout_path)
    for name, (path, data) in expected_layout.items():
        row = layout_rows.get(name)
        if row is not None:
            _services.dispatch(
                "_compare_scalar",
                errors,
                _services.dispatch("_relative", path, repo_root),
                "package_layout.current_status",
                expected=data.get("layout", {}).get("legacy_layout_status", _MISSING_VALUE),
                observed=row.get("current_status", _MISSING_VALUE),
            )

    topology_path = PACKAGE_MIRROR_OUTPUTS["test_topology"]
    topology = projection(topology_path)
    topology_rows = rows_index(topology.get("package"), "name", topology_path)
    exception_rows = rows_index(
        topology.get("source_package_exception"),
        "name",
        f"{topology_path}#source_package_exception",
    )
    dispositions = {"direct": 0, "explicit_source_exception": 0, "nested_coverage": 0}
    for name in sorted(set(topology_rows) - set(by_name) - set(exception_rows)):
        errors.append(
            _services.finding(
                "package-mirror",
                "error",
                topology_path,
                "topology row has neither a primary source contract nor explicit source exception",
                name,
            )
        )
    for name in sorted(set(by_name) & set(exception_rows) & set(topology_rows)):
        errors.append(
            _services.finding(
                "package-mirror",
                "error",
                topology_path,
                "primary package is both a direct topology row and source exception",
                name,
            )
        )

    def strict_descendant(parent: object, child: object) -> bool:
        if type(parent) is not str or type(child) is not str:
            return False
        p, c = PurePosixPath(parent), PurePosixPath(child)
        if (
            p.is_absolute()
            or c.is_absolute()
            or any(part in {".", ".."} for part in p.parts + c.parts)
        ):
            return False
        try:
            relative = c.relative_to(p)
        except ValueError:
            return False
        return bool(relative.parts)

    def nearest_topology_ancestor(data: dict[str, Any]) -> tuple[str, Path, dict[str, Any]] | None:
        package = data.get("package")
        if not isinstance(package, dict):
            return None
        module = package.get("module", _MISSING_VALUE)
        if type(module) is not str:
            return None
        candidates: list[tuple[str, Path, dict[str, Any]]] = []
        for candidate_module, (path, candidate) in by_module.items():
            candidate_package = candidate.get("package")
            candidate_name = (
                candidate_package.get("name", _MISSING_VALUE)
                if isinstance(candidate_package, dict)
                else _MISSING_VALUE
            )
            if (
                module.startswith(candidate_module + ".")
                and type(candidate_name) is str
                and candidate_name in topology_rows
            ):
                candidates.append((candidate_module, path, candidate))
        return max(candidates, key=lambda item: len(item[0].split("."))) if candidates else None

    for name, (path, data) in by_name.items():
        subject = _services.dispatch("_relative", path, repo_root)
        row = topology_rows.get(name)
        if row is not None:
            dispositions["direct"] += 1
            tests = source_table(data, "tests", subject)
            layout = source_table(data, "layout", subject)
            _services.dispatch(
                "_compare_scalar",
                errors,
                subject,
                "test_topology.source_path",
                expected=layout.get("source_root", _MISSING_VALUE),
                observed=row.get("source_path", _MISSING_VALUE),
            )
            _services.dispatch(
                "_compare_list",
                errors,
                subject,
                "test_topology.unit_path",
                expected=tests.get("unit_roots", _MISSING_VALUE),
                observed=[row.get("unit_path", _MISSING_VALUE)],
            )
            for kind in ("integration", "property"):
                source_required = tests.get(f"{kind}_required", _MISSING_VALUE)
                observed_table = row.get(kind, _MISSING_VALUE)
                if type(observed_table) is not dict:
                    _services.dispatch(
                        "_record_malformed_mirror_value",
                        errors,
                        subject,
                        f"test_topology.{kind}",
                        observed_table,
                        domain="table",
                        side="projection",
                    )
                    observed_required = _MISSING_VALUE
                    observed_path = _MISSING_VALUE
                else:
                    observed_required = observed_table.get("required", _MISSING_VALUE)
                    observed_path = observed_table.get("path", _MISSING_VALUE)
                _services.dispatch(
                    "_compare_boolean",
                    errors,
                    subject,
                    f"test_topology.{kind}.required",
                    expected=source_required,
                    observed=observed_required,
                )
                if type(source_required) is bool and type(observed_required) is bool:
                    source_roots = tests.get(f"{kind}_roots", _MISSING_VALUE)
                    if source_required is False and source_roots is _MISSING_VALUE:
                        source_roots = []
                    if observed_required is False and observed_path is _MISSING_VALUE:
                        observed_roots = []
                    else:
                        observed_roots = [observed_path]
                    _services.dispatch(
                        "_compare_list",
                        errors,
                        subject,
                        f"test_topology.{kind}.path",
                        expected=source_roots,
                        observed=observed_roots,
                    )
            continue
        exception = exception_rows.get(name)
        if exception is not None:
            dispositions["explicit_source_exception"] += 1
            layout = source_table(data, "layout", subject)
            _services.dispatch(
                "_compare_scalar",
                errors,
                subject,
                "test_topology.source_package_exception.source_path",
                expected=layout.get("source_root", _MISSING_VALUE),
                observed=exception.get("source_path", _MISSING_VALUE),
            )
            continue
        ancestor = nearest_topology_ancestor(data)
        if ancestor is None:
            errors.append(
                _services.finding(
                    "package-mirror",
                    "error",
                    subject,
                    "package has no direct topology row, exact source exception, "
                    "or structural parent",
                    name,
                )
            )
            continue
        _, _, ancestor_data = ancestor
        ancestor_name = ancestor_data["package"]["name"]
        ancestor_row = topology_rows[ancestor_name]
        child_layout = source_table(data, "layout", subject)
        parent_layout = source_table(
            ancestor_data, "layout", _services.dispatch("_relative", ancestor[1], repo_root)
        )
        child_source = child_layout.get("source_root", _MISSING_VALUE)
        parent_source = parent_layout.get("source_root", _MISSING_VALUE)
        _services.dispatch(
            "_validate_mirror_value",
            errors,
            subject,
            "layout.source_root",
            child_source,
            domain="string",
            side="source",
        )
        _services.dispatch(
            "_validate_mirror_value",
            errors,
            _services.dispatch("_relative", ancestor[1], repo_root),
            "layout.source_root",
            parent_source,
            domain="string",
            side="source",
        )
        if not strict_descendant(parent_source, child_source):
            errors.append(
                _services.finding(
                    "package-mirror",
                    "error",
                    subject,
                    "nested source is not strictly contained by its nearest module ancestor",
                    f"parent={parent_source!r} child={child_source!r}",
                )
            )
        child_tests = source_table(data, "tests", subject)
        unit_roots = child_tests.get("unit_roots", _MISSING_VALUE)
        parent_unit = ancestor_row.get("unit_path", _MISSING_VALUE)
        source_roots_valid = _services.dispatch(
            "_validate_mirror_value",
            errors,
            subject,
            "tests.unit_roots",
            unit_roots,
            domain="string_list",
            side="source",
        )
        parent_unit_valid = _services.dispatch(
            "_validate_mirror_value",
            errors,
            _services.dispatch("_relative", ancestor[1], repo_root),
            "test_topology.unit_path",
            parent_unit,
            domain="string",
            side="projection",
        )
        if (
            not source_roots_valid
            or not parent_unit_valid
            or not unit_roots
            or not all(strict_descendant(parent_unit, child) for child in unit_roots)
        ):
            errors.append(
                _services.finding(
                    "package-mirror",
                    "error",
                    subject,
                    "nested unit roots are not strictly covered by nearest ancestor topology",
                    f"parent={parent_unit!r} children={unit_roots!r}",
                )
            )
        for kind in ("integration", "property"):
            child_required = child_tests.get(f"{kind}_required", _MISSING_VALUE)
            if not _services.dispatch(
                "_validate_mirror_value",
                errors,
                subject,
                f"tests.{kind}_required",
                child_required,
                domain="boolean",
                side="source",
            ):
                continue
            child_roots = child_tests.get(f"{kind}_roots", _MISSING_VALUE)
            if child_required is False and child_roots is _MISSING_VALUE:
                child_roots = []
            child_roots_valid = _services.dispatch(
                "_validate_mirror_value",
                errors,
                subject,
                f"tests.{kind}_roots",
                child_roots,
                domain="string_list",
                side="source",
            )
            if not child_required:
                continue
            parent_table = ancestor_row.get(kind, _MISSING_VALUE)
            if not _services.dispatch(
                "_validate_mirror_value",
                errors,
                _services.dispatch("_relative", ancestor[1], repo_root),
                f"test_topology.{kind}",
                parent_table,
                domain="table",
                side="projection",
            ):
                continue
            parent_required = parent_table.get("required", _MISSING_VALUE)
            parent_required_valid = _services.dispatch(
                "_validate_mirror_value",
                errors,
                _services.dispatch("_relative", ancestor[1], repo_root),
                f"test_topology.{kind}.required",
                parent_required,
                domain="boolean",
                side="projection",
            )
            parent_root = parent_table.get("path", _MISSING_VALUE)
            parent_root_valid = _services.dispatch(
                "_validate_mirror_value",
                errors,
                _services.dispatch("_relative", ancestor[1], repo_root),
                f"test_topology.{kind}.path",
                parent_root,
                domain="string",
                side="projection",
            )
            if (
                not child_roots_valid
                or not parent_required_valid
                or not parent_root_valid
                or parent_required is not True
                or not child_roots
                or not all(strict_descendant(parent_root, child) for child in child_roots)
            ):
                errors.append(
                    _services.finding(
                        "package-mirror",
                        "error",
                        subject,
                        f"nested {kind} roots are not covered by nearest ancestor topology",
                        f"parent={parent_root!r} children={child_roots!r}",
                    )
                )
        dispositions["nested_coverage"] += 1

    summary = {
        "family_id": PACKAGE_MIRROR_FAMILY_ID,
        "source_contract_file_count": len(source_contracts),
        "primary_source_contract_count": len(primary),
        "projection_row_counts": {
            "boundaries": len(boundaries),
            "public_surface": len(public_rows),
            "layout": len(layout_rows),
            "topology": len(topology_rows),
        },
        "topology_source_dispositions": dispositions,
        "unmapped_public_surface_rows": unmapped_public_surface_rows,
        "registered_output_count": len(output_set),
    }
    return errors, summary
