#!/usr/bin/env python3
"""Install extension examples in editable mode and verify entry-point discovery."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from tools.lib.imports import repo_root_from

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

REPO_ROOT = repo_root_from(__file__)


@dataclass(frozen=True)
class ExampleSpec:
    """One installable extension example that must discover through entry points."""

    slug: str
    path: str
    group: str
    entry_point: str
    probe: str
    component_id: str | None = None
    kind: str | None = None
    abi_key: str | None = None
    pass_id: str | None = None


EXAMPLES: tuple[ExampleSpec, ...] = (
    ExampleSpec(
        slug="fabric_connector",
        path="examples/extensions/fabric_connector",
        group="polisyos.fabric_connectors",
        entry_point="example.local_rows",
        probe="fabric_connector",
        component_id="example.fabric_connector.local_rows@1.0.0",
        kind="fabric_connector",
        abi_key="fabric_connectors_api",
    ),
    ExampleSpec(
        slug="foundry_method",
        path="examples/extensions/foundry_method",
        group="polisyos.foundry_methods",
        entry_point="example.weighted_average",
        probe="foundry_method",
        component_id="example.summary.weighted_average@1.0.0",
        kind="foundry_method",
        abi_key="foundry_methods_api",
    ),
    ExampleSpec(
        slug="scientist_governance_pass",
        path="examples/extensions/scientist_governance_pass",
        group="polisyos.scientist_governance_passes",
        entry_point="example.audit_marker",
        probe="scientist_governance_pass",
        pass_id="example_audit_marker",  # noqa: S106 - governance pass identifier, not a secret.
    ),
    ExampleSpec(
        slug="scientist_node",
        path="examples/extensions/scientist_node",
        group="polisyos.scientist_nodes",
        entry_point="example.annotate_state",
        probe="scientist_node",
        component_id="example.scientist_node.annotate_state@1.0.0",
        kind="scientist_node",
        abi_key="scientist_nodes_api",
    ),
    ExampleSpec(
        slug="data_forge_domain",
        path="examples/extensions/data_forge_domain",
        group="polisyos.data_forge_domains",
        entry_point="example.city_budget",
        probe="data_forge_domain",
        component_id="example.data_forge_domain.city_budget@1.0.0",
        kind="data_forge_domain",
        abi_key="data_forge_domain_api",
    ),
    ExampleSpec(
        slug="lex_normpack",
        path="examples/extensions/lex_normpack",
        group="polisyos.lex_normpacks",
        entry_point="example.minimum_wage",
        probe="lex_normpack",
        component_id="example.lex_normpack.minimum_wage@1.0.0",
        kind="norm_pack_provider",
        abi_key="ir_abi",
    ),
    ExampleSpec(
        slug="runtime_middleware",
        path="examples/extensions/runtime_middleware",
        group="polisyos.runtime_middlewares",
        entry_point="example.response_header",
        probe="runtime_middleware",
        component_id="example.runtime_middleware.response_header@1.0.0",
        kind="runtime_middleware",
        abi_key="runtime_middleware_api",
    ),
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root containing examples/extensions.",
    )
    parser.add_argument(
        "--example",
        action="append",
        choices=[example.slug for example in EXAMPLES],
        default=[],
        help="Limit the gate to one or more examples.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Only validate pyproject structure; do not pip install examples.",
    )
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip importlib entry-point discovery verification.",
    )
    parser.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip each example's local smoke test.",
    )
    return parser


def selected_examples(slugs: Sequence[str] = ()) -> tuple[ExampleSpec, ...]:
    """Return examples filtered by the requested slugs."""
    if not slugs:
        return EXAMPLES
    selected = set(slugs)
    return tuple(example for example in EXAMPLES if example.slug in selected)


def validate_pyproject(repo_root: Path, examples: Iterable[ExampleSpec]) -> list[str]:
    """Return structural example-package errors."""
    errors: list[str] = []
    selected = tuple(examples)
    errors.extend(_validate_entry_point_coverage(repo_root, selected))
    for example in selected:
        root = repo_root / example.path
        pyproject = root / "pyproject.toml"
        readme = root / "README.md"
        smoke = root / "tests" / "test_smoke.py"
        if not pyproject.is_file():
            errors.append(f"{example.slug}: missing {pyproject.relative_to(repo_root)}")
            continue
        if not readme.is_file():
            errors.append(f"{example.slug}: missing {readme.relative_to(repo_root)}")
        if not smoke.is_file():
            errors.append(f"{example.slug}: missing {smoke.relative_to(repo_root)}")

        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        groups = data.get("project", {}).get("entry-points", {})
        declared_group = groups.get(example.group)
        if not isinstance(declared_group, dict):
            errors.append(f"{example.slug}: missing entry-point group {example.group}")
            continue
        if set(declared_group) != {example.entry_point}:
            errors.append(
                f"{example.slug}: expected exactly {example.entry_point!r} in {example.group}, "
                f"got {sorted(declared_group)}"
            )
    return errors


def _validate_entry_point_coverage(repo_root: Path, examples: Sequence[ExampleSpec]) -> list[str]:
    """Return errors for public extension-point groups missing example coverage."""
    architecture_path = repo_root / "architecture" / "extension_points.toml"
    pyproject_path = repo_root / "pyproject.toml"
    if not architecture_path.is_file() or not pyproject_path.is_file():
        return []

    architecture = tomllib.loads(architecture_path.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project_entry_points = pyproject.get("project", {}).get("entry-points", {})
    if not isinstance(project_entry_points, dict):
        project_entry_points = {}

    example_paths = {example.path for example in examples}
    example_groups = {example.group for example in examples}
    contract_groups: set[str] = set()
    for row in architecture.get("extension_point", []):
        if not isinstance(row, dict):
            continue
        group = _string_field(row, "entry_point_group") or _string_field(row, "name")
        if group is not None:
            contract_groups.add(group)
        legacy_groups = row.get("legacy_entry_point_groups", [])
        if isinstance(legacy_groups, list):
            contract_groups.update(
                str(item).strip() for item in legacy_groups if str(item).strip()
            )

    errors: list[str] = []
    for group in sorted(project_entry_points):
        if group not in contract_groups:
            errors.append(
                f"{group}: entry-point group in pyproject.toml must be declared in "
                "architecture/extension_points.toml"
            )

    for row in architecture.get("extension_point", []):
        if not isinstance(row, dict):
            continue
        group = _string_field(row, "entry_point_group") or _string_field(row, "name")
        if group is None:
            continue

        if group not in project_entry_points:
            errors.append(f"{group}: extension point is missing from pyproject.toml entry-points")
            continue

        if row.get("internal_only") is True:
            if not _string_field(row, "owner"):
                errors.append(f"{group}: internal_only exception requires owner")
            if not _has_review_date(row):
                errors.append(
                    f"{group}: internal_only exception requires internal_only_review_date"
                )
            continue

        example_package = _string_field(row, "example_package")
        if example_package is None or not _is_extension_example_path(example_package):
            errors.append(
                f"{group}: public entry-point group must declare example_package "
                "under examples/extensions/** or internal_only = true"
            )
            continue

        if example_package not in example_paths or group not in example_groups:
            errors.append(
                f"{group}: example_package {example_package} is not covered by "
                "tools/quality/validation/check_extension_examples.py"
            )

    return errors


def _string_field(row: Mapping[str, object], key: str) -> str | None:
    value = row.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _has_review_date(row: Mapping[str, object]) -> bool:
    value = row.get("internal_only_review_date")
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None and hasattr(value, "isoformat")


def _is_extension_example_path(value: str) -> bool:
    parts = PurePosixPath(value).parts
    return (
        len(parts) >= 3
        and parts[0] == "examples"
        and parts[1] == "extensions"
        and all(part not in {"", ".", ".."} for part in parts)
    )


def install_examples(repo_root: Path, examples: Iterable[ExampleSpec]) -> None:
    """Install all examples in editable mode into the active Python environment."""
    for example in examples:
        example_path = repo_root / example.path
        print(f"[extension-examples] install -e {example.path}")
        _install_editable(example_path)


def _install_editable(path: Path) -> None:
    pip_cmd = [sys.executable, "-m", "pip"]
    if _command_ok([*pip_cmd, "--version"]):
        subprocess.run(  # noqa: S603
            [
                *pip_cmd,
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                "-e",
                str(path),
            ],
            check=True,
        )
        return

    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("Neither `python -m pip` nor `uv pip` is available for editable install")
    subprocess.run(  # noqa: S603
        [uv, "pip", "install", "--python", sys.executable, "--no-deps", "-e", str(path)],
        check=True,
    )


def _command_ok(argv: Sequence[str]) -> bool:
    return subprocess.run(argv, check=False, capture_output=True, text=True).returncode == 0  # noqa: S603


def verify_discovery(examples: Iterable[ExampleSpec]) -> None:
    """Run discovery in a fresh interpreter so installed entry points are visible."""
    selected = tuple(examples)
    component_examples = tuple(example for example in selected if example.component_id is not None)
    governance_pass_examples = tuple(
        example for example in selected if example.probe == "scientist_governance_pass"
    )
    if component_examples:
        payload = json.dumps([asdict(example) for example in component_examples], sort_keys=True)
        subprocess.run(  # noqa: S603
            [sys.executable, "-c", _COMPONENT_DISCOVERY_SNIPPET, payload],
            check=True,
        )
    if governance_pass_examples:
        payload = json.dumps(
            [asdict(example) for example in governance_pass_examples],
            sort_keys=True,
        )
        subprocess.run(  # noqa: S603
            [sys.executable, "-c", _GOVERNANCE_PASS_DISCOVERY_SNIPPET, payload],
            check=True,
        )


def run_example_tests(repo_root: Path, examples: Iterable[ExampleSpec]) -> None:
    """Run each example's local smoke test after editable install."""
    test_paths = [str(repo_root / example.path / "tests") for example in examples]
    if not test_paths:
        return
    subprocess.run([sys.executable, "-m", "pytest", "-q", *test_paths], cwd=repo_root, check=True)  # noqa: S603


_COMPONENT_DISCOVERY_SNIPPET = r"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from polisyos.core.components import discover_components
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _assert_probe(spec: dict[str, str], created: object) -> None:
    probe = spec["probe"]
    if probe == "fabric_connector":
        assert created.fetch_preview()[0]["value"] == 42
        return
    if probe == "foundry_method":
        assert created.pure_step({"values": [1, 3, 5], "weights": [1, 2, 1]}, {}) == {"mean": 3.0}
        return
    if probe == "scientist_node":
        outcome = created.execute(ctx=None, state=ExperimentState(run_id="example-discovery"))
        assert outcome.state.params["example_node_seen"] is True
        return
    if probe == "data_forge_domain":
        assert created.materialize()[0]["program"] == "transit"
        return
    if probe == "lex_normpack":
        pack = created.get_static_norm_pack(cas=None, jurisdiction="EX", domain="labor", as_of="2026-01-01")
        assert pack.norms[0].norm_id == "norm.example.minimum_wage.floor"
        return
    if probe == "runtime_middleware":
        messages: list[dict[str, Any]] = []

        async def app(scope, receive, send) -> None:
            del scope, receive
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        asyncio.run(created(app)({"type": "http", "path": "/"}, receive, send))
        assert messages[0]["headers"] == [(b"x-polisyos-example", b"runtime-middleware")]
        return
    raise AssertionError(f"unknown probe: {probe}")


specs = json.loads(sys.argv[1])
by_group: dict[str, list[dict[str, str]]] = {}
for spec in specs:
    by_group.setdefault(spec["group"], []).append(spec)

for group, group_specs in sorted(by_group.items()):
    report = discover_components(groups=[group], include_dev_scan=False)
    assert report.errors == [], [error.message for error in report.errors]
    discovered = {str(item.metadata.component_id): item for item in report.components}
    for spec in group_specs:
        item = discovered.get(spec["component_id"])
        assert item is not None, f"{spec['component_id']} not discovered in {group}"
        metadata = item.metadata
        assert metadata.kind.value == spec["kind"]
        assert spec["abi_key"] in metadata.abi_targets
        assert item.source.source_type == "entry_point"
        assert item.source.group == group
        assert item.source.entry_point == spec["entry_point"]
        _assert_probe(spec, item.component.create())

print(f"discovered {len(specs)} extension examples")
"""


_GOVERNANCE_PASS_DISCOVERY_SNIPPET = r"""  # noqa: S105 - embedded probe code uses pass_id.
from __future__ import annotations

import json
import sys

from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.scientist.governance.pass_registry import load_governance_passes


specs = json.loads(sys.argv[1])
validators = load_governance_passes()
by_pass_id = {validator.pass_id: validator for validator in validators}

for spec in specs:
    pass_id = spec["pass_id"]
    validator = by_pass_id.get(pass_id)
    assert validator is not None, f"{pass_id} not discovered in {spec['group']}"
    assert isinstance(validator, ValidatorPass)
    ctx = PassContext(
        ir=None,
        state={"example_governance_approved": True},
        registry_bundle=None,
        profile=ValidationProfile.fast(),
        run_id="example-governance-discovery",
    )
    assert validator.validate(ctx) == []

print(f"discovered {len(specs)} governance pass extension example(s)")
"""


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    examples = selected_examples(args.example)

    errors = validate_pyproject(repo_root, examples)
    if errors:
        print("Extension example package validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    if not args.skip_install:
        install_examples(repo_root, examples)
    if not args.skip_discovery:
        verify_discovery(examples)
    if not args.skip_pytest:
        run_example_tests(repo_root, examples)

    print(f"Extension example gate passed for {len(examples)} example(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
