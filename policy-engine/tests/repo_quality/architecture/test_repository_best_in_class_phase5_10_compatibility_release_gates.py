from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest

from tools.ops_runners.release import check_compatibility_release_gates as gates
from tools.ops_runners.release.build_release_notes import load_fragments, render_release_notes

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase5_10_compatibility_release_gate_contract_is_report_only() -> None:
    contract = _read_toml("architecture/gates/compatibility_release.toml")
    header = contract["compatibility_release_gates"]
    checks = {item["id"]: item for item in contract["promotion_check"]}

    assert header["status"] == "report_only"
    assert header["mode"] == "report_only"
    assert header["gate_command"] == (
        "uv run polisyos-tools release check-compatibility-release-gates --fail-on-contract-errors"
    )
    assert {
        "breaking-compatibility-fragment",
        "migration-runbook-docs",
        "public-surface-inventory-review",
        "generated-client-compatibility",
    } == set(checks)
    for check in checks.values():
        assert check["mode"] == "report_only", check["id"]
        assert check["owner"].startswith("team-"), check["id"]
        for source in check["source_contracts"]:
            assert _path_or_glob_exists(source), (check["id"], source)


def test_phase5_10_compatibility_promises_have_owner_and_window() -> None:
    report = gates.build_report(repo_root=REPO_ROOT)

    non_review_errors = [
        item for item in report["contract_errors"] if item["check"] != "public-surface-review"
    ]
    assert not non_review_errors, non_review_errors
    assert report["structured_compatibility_change_count"] >= 1


def test_phase5_10_release_tool_is_registered() -> None:
    from tools.registry import TOOL_SPECS_BY_KEY

    spec = TOOL_SPECS_BY_KEY[("release", "check-compatibility-release-gates")]

    assert spec.module == "tools.ops_runners.release.check_compatibility_release_gates"
    assert spec.callable_name == "main"
    assert spec.status.value == "active"


def test_phase5_10_checker_reports_breaking_class_without_fragment(tmp_path: Path) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()

    report = gates.build_report(
        repo_root=REPO_ROOT,
        fragments_dir=fragments,
        breaking_classes=("schema-openapi-abi",),
    )

    messages = {
        item["message"]
        for item in report["contract_errors"]
        if item["check"] == "breaking-fragment"
    }
    assert "breaking compatibility class has no structured release fragment" in messages


def test_phase5_10_checker_rejects_parseable_but_unrenderable_fragment(tmp_path: Path) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    fragment_path = fragments / "nested-metadata.toml"
    fragment_path.write_text(
        """
[change]
area = "runtime"
summary = "A runtime change."

[public_surface]
id = "nested-metadata"
title = "Nested metadata"
type = "changed"
owner = "team-runtime"
summary = "This fragment parses but has no top-level release fields."
evidence = ["tests/example.py"]
""",
        encoding="utf-8",
    )

    report = gates.build_report(repo_root=REPO_ROOT, fragments_dir=fragments)
    schema_errors = [
        item for item in report["contract_errors"] if item["check"] == "fragment-schema"
    ]
    assert {item["message"] for item in schema_errors} >= {
        "missing `id`",
        "missing `title`",
        "missing `type`",
        "missing `owner`",
        "missing `summary`",
        "missing `evidence`",
    }

    loaded = load_fragments(fragments)
    with pytest.raises(KeyError, match=r"^'type'$") as error:
        render_release_notes("0.0.0", loaded, "2026-10-11")
    assert error.value.args == ("type",)


def test_phase5_10_checker_rejects_unsupported_nonempty_fragment_type(
    tmp_path: Path,
) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    fragment_path = fragments / "unsupported-type.toml"
    fragment_path.write_text(
        """
id = "unsupported-type"
title = "Unsupported type"
type = "internal"
owner = "team-runtime"
summary = "This fragment has a nonempty unsupported renderer category."
evidence = ["tests/example.py"]
""",
        encoding="utf-8",
    )

    report = gates.build_report(repo_root=REPO_ROOT, fragments_dir=fragments)
    schema_errors = [
        item
        for item in report["contract_errors"]
        if item["check"] == "fragment-schema"
        and item["subject"].endswith("unsupported-type.toml")
    ]
    assert any(
        item["message"] == "unsupported fragment type" and item["detail"] == "internal"
        for item in schema_errors
    )

    loaded = load_fragments(fragments)
    with pytest.raises(ValueError, match=r"unsupported fragment type `internal`") as error:
        render_release_notes("0.0.0", loaded, "2026-10-11")
    assert error.value.args == (
        f"{fragment_path}: unsupported fragment type `internal`",
    )


def test_phase5_10_checker_rejects_whitespace_root_fields_and_malformed_evidence(
    tmp_path: Path,
) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    fragment_path = fragments / "whitespace-root-fields.toml"
    fragment_path.write_text(
        '''
id = "  "
title = "\\t"
type = " "
owner = "  "
summary = "\\t"
evidence = "tests/example.py"
''',
        encoding="utf-8",
    )

    report = gates.build_report(repo_root=REPO_ROOT, fragments_dir=fragments)
    schema_errors = [
        item
        for item in report["contract_errors"]
        if item["check"] == "fragment-schema" and item["subject"].endswith(fragment_path.name)
    ]
    assert {item["message"] for item in schema_errors} >= {
        "missing `id`",
        "missing `title`",
        "missing `type`",
        "missing `owner`",
        "missing `summary`",
        "invalid `evidence`; expected a non-empty list of non-empty strings",
    }

    loaded = load_fragments(fragments)
    with pytest.raises(ValueError, match=r"unsupported fragment type ``"):
        render_release_notes("0.0.0", loaded, "2026-10-11")


def test_phase5_10_checker_rejects_unknown_generated_client_values(
    tmp_path: Path,
) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    (fragments / "unknown-generated-client.toml").write_text(
        """
id = "unknown-generated-client"
title = "Unknown generated client status"
type = "changed"
owner = "team-runtime"
summary = "Both root and structured statuses must use the declared enum."
evidence = ["tests/example.py"]
generated_client_compatibility = "unchanged"

[[compatibility_change]]
id = "typed-change"
change_class = "schema-openapi-abi"
impact = "additive"
surface = "api: /example"
owner = "team-runtime"
version_owner = "team-runtime"
deprecation_window = "not_applicable"
release_note = "An additive API change."
generated_client_compatibility = "additive-optional-field"
""",
        encoding="utf-8",
    )

    report = gates.build_report(repo_root=REPO_ROOT, fragments_dir=fragments)
    enum_errors = [
        item
        for item in report["contract_errors"]
        if item["check"] == "generated-client-enum"
    ]
    assert len(enum_errors) == 2, enum_errors
    assert {item["detail"] for item in enum_errors} == {
        "'unchanged'",
        "'additive-optional-field'",
    }


def test_phase5_10_checker_matches_policy_types_to_real_renderer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    monkeypatch.setitem(gates.SECTION_TITLES, "internal", "Internal")

    report = gates.build_report(repo_root=REPO_ROOT, fragments_dir=fragments)

    contract_errors = [
        item
        for item in report["contract_errors"]
        if item["check"] == "fragment-schema-policy"
    ]
    assert len(contract_errors) == 1, contract_errors
    assert contract_errors[0]["message"] == (
        "allowed fragment types do not match release-note renderer categories"
    )


def test_phase5_10_checker_accepts_breaking_fragment_with_docs(tmp_path: Path) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    (fragments / "breaking.toml").write_text(
        """
id = "test-breaking-runtime-state"
title = "Runtime state migration"
type = "changed"
component = "runtime"
owner = "team-ops"
summary = "Runtime-state reader compatibility changed."
evidence = ["tests/example.py"]
compatibility = "Runtime-state readers need the migration guide."
change_class = "runtime-state-format"
surface_classification = "public_stable: polisyos.runtime"
migration = "Follow the migration guide."
api = "No runtime HTTP API change."
limitations = "Operators must retain exported state until rollout finishes."
generated_client_compatibility = "not_applicable"
public_surface_inventory_reviewed = false
migration_docs = ["docs/runbooks/migration-release-promotion.md"]
runbook_docs = ["docs/runbooks/migration-release-promotion.md"]

[[compatibility_change]]
id = "runtime-state-reader-v2"
change_class = "runtime-state-format"
impact = "breaking"
surface = "public_stable: polisyos.runtime"
owner = "team-ops"
version_owner = "team-ops"
deprecation_window = "1 major release"
release_note = "Runtime-state readers require the documented migration path."
generated_client_compatibility = "not_applicable"
migration_docs = ["docs/runbooks/migration-release-promotion.md"]
runbook_docs = ["docs/runbooks/migration-release-promotion.md"]
""",
        encoding="utf-8",
    )

    report = gates.build_report(
        repo_root=REPO_ROOT,
        fragments_dir=fragments,
        breaking_classes=("runtime-state-format",),
    )

    assert report["contract_error_count"] == 0, report["contract_errors"]
    rendered = render_release_notes("1.0.0", load_fragments(fragments), "2026-10-11")
    assert "Runtime state migration" in rendered
    assert "Runtime-state readers require the documented migration path." in rendered


def test_root_change_class_is_legacy_prose_and_structured_class_is_enum_gated(
    tmp_path: Path,
) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    fragment_path = fragments / "legacy-root-class.toml"
    fragment_path.write_text(
        """
id = "legacy-root-class"
title = "Legacy class rendering"
type = "changed"
owner = "team-runtime"
summary = "Root classification remains descriptive prose."
evidence = ["tests/example.py"]
change_class = "composite: API plus runtime behavior"

[[compatibility_change]]
id = "structured-change"
change_class = "not-a-policy-enum"
impact = "additive"
surface = "api: /example"
owner = "team-runtime"
version_owner = "team-runtime"
deprecation_window = "not_applicable"
release_note = "A structured compatibility row with an invalid class."
""",
        encoding="utf-8",
    )

    report = gates.build_report(repo_root=REPO_ROOT, fragments_dir=fragments)
    invalid_structured_class = [
        item
        for item in report["contract_errors"]
        if item["check"] == "fragment-compatibility"
        and item["message"] == "unsupported change_class"
    ]
    assert len(invalid_structured_class) == 1
    assert invalid_structured_class[0]["detail"] == "not-a-policy-enum"
    assert report["contract_errors"] == invalid_structured_class

    rendered = render_release_notes("0.0.0", load_fragments(fragments), "2026-10-11")
    assert "## Change Classes\n- composite: API plus runtime behavior" in rendered
    assert "## Structured Compatibility Changes" in rendered


def test_phase5_10_cli_contract_check_passes_or_reports_inventory_hold() -> None:
    env = os.environ.copy()
    env["POLISYOS_NATIVE_RELEASE_OVERLAY"] = "1"
    result = subprocess.run(
        [
            "uv",
            "run",
            "polisyos-tools",
            "release",
            "check-compatibility-release-gates",
            "--fail-on-contract-errors",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    report = json.loads(result.stdout)
    assert report["phase"] == "repository-best-in-class-phase-5.10"
    assert result.returncode in (0, 1)
    assert report["contract_error_count"] == len(report["contract_errors"])
    assert all(
        item["check"] == "public-surface-review" for item in report["contract_errors"]
    )
    if result.returncode == 0:
        assert not report["contract_errors"]
    else:
        assert report["contract_errors"]


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def _path_or_glob_exists(path: str) -> bool:
    if any(char in path for char in "*?["):
        return bool(list(REPO_ROOT.glob(path)))
    return (REPO_ROOT / path).exists()
