"""Check CI Python declarations against the project's declared interpreter range.

Literal major.minor and major.minor.patch versions, static matrix values (including
include rows), local action defaults, and literal version files are supported.
Unknown expressions fail closed. Matrix exclusions are deliberately conservative:
every declared candidate must be supported, even if an exclusion would remove it.
Include rows must name the referenced axis; implicit inheritance is not resolved.
This does not interpret shell commands or externally supplied workflow input values.
"""

from __future__ import annotations

import argparse
import os
import re
import tomllib
from pathlib import Path
from typing import Any

import yaml
from packaging.specifiers import SpecifierSet
from packaging.version import Version

EXPRESSION = re.compile(r"\$\{\{\s*(matrix|inputs)\.([A-Za-z_][\w-]*)\s*\}\}")
LITERAL = re.compile(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?")
POLICY_ACTION = "./.github/actions/setup-policy-engine-python"


def mapping(value: Any, location: str) -> dict[str, Any]:
    """Require a YAML mapping rather than silently ignoring an unknown shape."""
    if not isinstance(value, dict):
        raise ValueError(f"{location}: expected a mapping")
    return value


def resolve_values(value: Any, context: dict[str, Any]) -> list[str]:
    """Resolve a literal or a static matrix/input reference without evaluating code."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing or non-string Python declaration: {value!r}")
    value = value.strip()
    expression = EXPRESSION.fullmatch(value)
    if expression is None:
        if "${{" in value:
            raise ValueError(f"unresolved Python expression: {value}")
        return [value]
    kind, key = expression.groups()
    if kind == "inputs":
        inputs = mapping(context.get("inputs", {}), "inputs")
        definition = mapping(inputs.get(key), f"inputs.{key}")
        default = definition.get("default")
        if not isinstance(default, str) or "${{" in default:
            raise ValueError(f"inputs.{key}: no literal default")
        return [default]
    matrix = mapping(context.get("matrix"), "strategy.matrix")
    values = matrix.get(key, [])
    if not isinstance(values, list):
        raise ValueError(f"matrix.{key}: expected a static list")
    values = list(values)
    includes = matrix.get("include", [])
    if not isinstance(includes, list):
        raise ValueError("matrix.include: expected a static list")
    for row in includes:
        row = mapping(row, "matrix.include row")
        if key not in row:
            raise ValueError(f"matrix.include row: {key} inheritance is unresolved")
        values.append(row[key])
    if not values or any(not isinstance(item, str) or "${{" in item for item in values):
        raise ValueError(f"matrix.{key}: missing or unresolved candidates")
    return values


def supported_literal(value: str, requirement: SpecifierSet) -> bool:
    """Require the entire version selection to fit the declared Python range."""
    if not LITERAL.fullmatch(value):
        raise ValueError(f"unsupported or malformed Python version: {value!r}")
    lower = Version(value)
    if len(lower.release) == 3:
        return lower in requirement
    # setup-python's major.minor selector can select any patch in that minor.
    upper = Version(f"{lower.major}.{lower.minor + 1}")
    for specifier in requirement:
        operator, bound = specifier.operator, specifier.version
        wildcard = bound.endswith(".*")
        boundary = Version(bound.removesuffix(".*"))
        wildcard_upper = None
        if wildcard:
            release = list(boundary.release)
            release[-1] += 1
            wildcard_upper = Version(".".join(map(str, release)))
        if operator == ">=" and lower < boundary:
            return False
        if operator == ">" and lower <= boundary:
            return False
        if operator in {"<", "<="} and upper > boundary:
            return False
        if operator in {"==", "==="}:
            if wildcard_upper is None or lower < boundary or upper > wildcard_upper:
                return False
        if operator == "!=":
            if wildcard_upper is not None and lower < wildcard_upper and upper > boundary:
                return False
            if not wildcard and lower <= boundary < upper:
                return False
        if operator == "~=":
            release = list(boundary.release[:-1])
            release[-1] += 1
            compatible_upper = Version(".".join(map(str, release)))
            if lower < boundary or upper > compatible_upper:
                return False
    return lower in requirement


def check_versions(repo_root: Path) -> int:
    """Walk CI YAML declarations and report every unsupported or undecidable pin."""
    project = repo_root / "policy-engine"
    with (project / "pyproject.toml").open("rb") as source:
        requirement = SpecifierSet(tomllib.load(source)["project"]["requires-python"])
    errors: list[str] = []
    checked = 0

    def validate(value: str, location: str) -> None:
        nonlocal checked
        checked += 1
        if not supported_literal(value, requirement):
            errors.append(f"{location}: Python {value} is outside {requirement}")

    documents: dict[str, Any] = {}
    ci_root = repo_root / ".github"
    if not ci_root.is_dir():
        raise ValueError(f"CI declaration directory is missing: {ci_root}")

    def unreadable(error: OSError) -> None:
        raise error

    for directory, names, files in os.walk(ci_root, onerror=unreadable):
        if any((Path(directory) / name).is_symlink() for name in names):
            raise ValueError(f"unsupported symlink declaration directory: {directory}")
        for name in sorted(files):
            path = Path(directory) / name
            if path.suffix not in {".yml", ".yaml"}:
                continue
            relative = str(path.relative_to(repo_root))
            documents[relative] = yaml.safe_load(path.read_text(encoding="utf-8"))
    policy_action = documents.get(f"{POLICY_ACTION[2:]}/action.yml")
    if policy_action is None:
        raise ValueError("Policy Engine setup action is missing")
    policy_inputs = mapping(
        mapping(policy_action, "Policy Engine setup action").get("inputs"),
        "Policy Engine setup inputs",
    )
    default = mapping(policy_inputs.get("python-version"), "python-version input").get("default")

    def walk(node: Any, location: str, context: dict[str, Any]) -> None:
        if isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{location}[{index}]", context)
            return
        if not isinstance(node, dict):
            return
        if "strategy" in node:
            strategy = mapping(node["strategy"], f"{location}.strategy")
            context = {**context, "matrix": strategy.get("matrix")}
        uses = node.get("uses", "")
        options = node.get("with", {})
        declares_version = isinstance(options, dict) and (
            "python-version" in options or "python-version-file" in options
        )
        if declares_version or uses == POLICY_ACTION or str(uses).startswith("actions/setup-python@"):
            try:
                options = mapping(options, f"{location}.with")
                if "python-version" in options and "python-version-file" in options:
                    raise ValueError("declare either python-version or python-version-file")
                if "python-version-file" in options:
                    for filename in resolve_values(options["python-version-file"], context):
                        source = (repo_root / filename).resolve(strict=True)
                        if not source.is_relative_to(repo_root):
                            raise ValueError(f"version file escapes repository: {filename}")
                        validate(source.read_text(encoding="utf-8").strip(), location)
                else:
                    value = options.get("python-version", default if uses == POLICY_ACTION else None)
                    for version in resolve_values(value, context):
                        validate(version, location)
            except (OSError, ValueError) as error:
                errors.append(f"{location}: {error}")
        for key, child in node.items():
            walk(child, f"{location}.{key}", context)

    try:
        validate((project / ".python-version").read_text(encoding="utf-8").strip(), ".python-version")
        for relative, document in sorted(documents.items()):
            if not isinstance(document, dict):
                walk(document, relative, {})
                continue
            inputs = document.get("inputs", {})
            # PyYAML's YAML 1.1 resolver reads an unquoted `on` key as True.
            events = document.get("on", document.get(True))
            if isinstance(events, dict):
                for event in ("workflow_call", "workflow_dispatch"):
                    definition = events.get(event, {})
                    if isinstance(definition, dict):
                        inputs = {**inputs, **definition.get("inputs", {})}
            if "python-version" in inputs:
                for value in resolve_values("${{ inputs.python-version }}", {"inputs": inputs}):
                    validate(value, f"{relative}.inputs.python-version.default")
            walk(document, relative, {"inputs": inputs})
    except (OSError, ValueError) as error:
        errors.append(str(error))
    for error in errors:
        print(error)
    print(
        f"CI YAML files={len(documents)}; Python version candidates={checked}; "
        f"invalid or undecidable={len(errors)}; requires-python={requirement}"
    )
    return int(bool(errors))


def main() -> int:
    """Run the range gate, refusing an unreadable or malformed declaration set."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        return check_versions(args.repo_root.resolve(strict=True))
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        print(f"Unable to verify CI Python declarations: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
