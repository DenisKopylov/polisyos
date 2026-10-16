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
        if item["check"] == "fragment-schema" and item["subject"].endswith("unsupported-type.toml")
    ]
    assert any(
        item["message"] == "unsupported fragment type" and item["detail"] == "internal"
        for item in schema_errors
    )

    loaded = load_fragments(fragments)
    with pytest.raises(ValueError, match=r"unsupported fragment type `internal`") as error:
        render_release_notes("0.0.0", loaded, "2026-10-11")
    assert error.value.args == (f"{fragment_path}: unsupported fragment type `internal`",)


def test_phase5_10_checker_rejects_whitespace_root_fields_and_malformed_evidence(
    tmp_path: Path,
) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    fragment_path = fragments / "whitespace-root-fields.toml"
    fragment_path.write_text(
        """
id = "  "
title = "\\t"
type = " "
owner = "  "
summary = "\\t"
evidence = "tests/example.py"
""",
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
        item for item in report["contract_errors"] if item["check"] == "generated-client-enum"
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
        item for item in report["contract_errors"] if item["check"] == "fragment-schema-policy"
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


def _write_public_surface_inventory_fixture(root: Path) -> None:
    from tools.devx.architecture import guardrails as public_surface_guardrails

    architecture = root / "architecture" / "public_surface"
    architecture.mkdir(parents=True)
    (architecture / "contract.toml").write_text(
        """
[public_surface]
version_owner = "team-architecture"
deprecation_window = "2 minor releases"
release_fragment_change_class = "python-public-api"
inventory = "architecture/public_surface/inventory.json"
inventory_regenerate_command = "uv run python tools/devx/architecture/guardrails.py sync"
inventory_review_owner = "team-architecture"
inventory_review_policy = "Review the exact generated route set."

[[package]]
module = "polisyos.fixture"
classification = "public_stable"
facade_mode = "lazy_facade"
owner = "team-fixture"
readme = "src/polisyos/fixture/README.md"
reference_doc = "docs/reference/public-surface.md"
supported_entrypoints = ["polisyos.fixture", "polisyos.fixture.api"]
major_subsystem = false

[[generated_artifact_family]]
id = "fixture-family"
owner = "team-fixture"
regenerate = "python tools/fixture.py"
stale_output_behavior = "fail"
outputs = ["architecture/fixture.json"]
""",
        encoding="utf-8",
    )
    entrypoint = public_surface_guardrails.SupportedEntrypointInventory(
        module="polisyos.fixture",
        facade_mode_observed="lazy_facade",
        export_count=0,
        known_export_count=0,
        exports=(),
        has___getattr__=False,
        has___dir__=False,
        source_file="src/polisyos/fixture/__init__.py",
        summary="Fixture facade.",
        export_resolution={"complete": True},
    )
    package = public_surface_guardrails.PackageInventory(
        module="polisyos.fixture",
        classification="public_stable",
        facade_mode_expected="lazy_facade",
        facade_mode_observed="lazy_facade",
        owner="team-fixture",
        readme="src/polisyos/fixture/README.md",
        reference_doc="docs/reference/public-surface.md",
        supported_entrypoints=("polisyos.fixture", "polisyos.fixture.api"),
        major_subsystem=False,
        export_count=0,
        known_export_count=0,
        exports=(),
        has___getattr__=False,
        has___dir__=False,
        source_file="src/polisyos/fixture/__init__.py",
        summary="Fixture facade.",
        notes="",
        entrypoints=(
            entrypoint,
            public_surface_guardrails.SupportedEntrypointInventory(
                module="polisyos.fixture.api",
                facade_mode_observed="eager_exports",
                export_count=0,
                known_export_count=0,
                exports=(),
                has___getattr__=False,
                has___dir__=False,
                source_file="src/polisyos/fixture/api.py",
                summary="Fixture API.",
                export_resolution={"complete": True},
            ),
        ),
    )
    family = public_surface_guardrails.PublicGeneratedArtifactFamily(
        family_id="fixture-family",
        owner="team-fixture",
        regenerate="python tools/fixture.py",
        stale_output_behavior="fail",
        outputs=("architecture/fixture.json",),
    )
    inventory = json.loads(
        public_surface_guardrails.render_public_surface_json(
            [package], generated_artifact_families=[family]
        )
    )
    (architecture / "inventory.json").write_text(
        json.dumps(inventory, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_public_surface_report(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    policy_path = root / "release-policy.toml"
    policy_path.write_text(
        """
[compatibility_release_gates]
status = "report_only"
mode = "report_only"
release_fragment_unreleased_root = "fragments"
public_surface_contract = "architecture/public_surface/contract.toml"
public_surface_inventory = "architecture/public_surface/inventory.json"
""",
        encoding="utf-8",
    )
    fragments = root / "fragments"
    fragments.mkdir(exist_ok=True)
    for name in (
        "_validate_policy",
        "_validate_extension_points",
        "_validate_generated_artifacts",
        "_validate_runtime_state",
        "_validate_migrations",
        "_validate_schema_manifests",
        "_validate_release_template",
    ):
        monkeypatch.setattr(gates, name, lambda *args, **kwargs: [])
    monkeypatch.setattr(gates, "_validate_fragments", lambda *args, **kwargs: ([], []))
    return gates.build_report(
        repo_root=root,
        policy_path=policy_path,
        fragments_dir=fragments,
    )


def test_phase5_10_public_surface_report_reconciles_complete_declaration_sets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_public_surface_inventory_fixture(tmp_path)
    report = _run_public_surface_report(tmp_path, monkeypatch)

    evidence = report["public_surface_inventory_evidence"]
    assert report["contract_errors"] == []
    assert evidence["complete_verdict"] is True
    assert evidence["predicate_status"] == "consistent"
    denominator = evidence["denominator"]
    assert denominator["contract_package_rows"] == 1
    assert denominator["inventory_package_rows"] == 1
    assert denominator["canonical_package_model_fields_per_row"] > 0
    assert denominator["contract_package_model_field_slots_present"] == (
        denominator["contract_package_model_field_slots_expected"] - 1
    )  # The canonical parser supplies the omitted optional `notes` default.
    assert (
        denominator["inventory_package_schema_field_slots_present"]
        == (denominator["inventory_package_schema_field_slots_expected"])
    )
    assert denominator["contract_supported_entrypoints"] == 2
    assert denominator["inventory_supported_entrypoints"] == 2
    assert denominator["inventory_entrypoint_rows"] == 2
    assert denominator["contract_generated_artifact_families"] == 1
    assert denominator["inventory_generated_artifact_families"] == 1
    inputs = {item["path"]: item for item in evidence["inputs"]}
    assert {
        "architecture/public_surface/contract.toml",
        "architecture/public_surface/inventory.json",
    } <= set(inputs)
    assert any(path.endswith("tools/devx/architecture/guardrails.py") for path in inputs)
    assert all(item["status"] == "read" and len(item["sha256"]) == 64 for item in inputs.values())


def test_phase5_10_public_surface_unavailable_canonical_renderer_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_public_surface_inventory_fixture(tmp_path)

    def unavailable_canonical_renderer() -> tuple[object, dict[str, str], dict[str, Any]]:
        raise ModuleNotFoundError("No module named 'polisyos.common.markdown'")

    monkeypatch.setattr(gates, "_canonical_public_surface_context", unavailable_canonical_renderer)
    report = _run_public_surface_report(tmp_path, monkeypatch)

    unavailable_errors = [
        error
        for error in report["contract_errors"]
        if error["subject"] == "tools/devx/architecture/guardrails.py"
        and error["message"] == "canonical public-surface model or renderer is unavailable"
    ]
    evidence = report["public_surface_inventory_evidence"]
    assert len(unavailable_errors) == 1
    assert evidence["complete_verdict"] is False
    assert evidence["predicate_status"] == "not_established"


def test_phase5_10_public_surface_route_removal_fails_with_inventory_markers_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_public_surface_inventory_fixture(tmp_path)
    inventory_path = tmp_path / "architecture/public_surface/inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    package = inventory["packages"][0]
    package["supported_entrypoints"].remove("polisyos.fixture.api")
    package["entrypoints"].pop()
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    report = _run_public_surface_report(tmp_path, monkeypatch)
    route_errors = [
        error
        for error in report["contract_errors"]
        if error["message"] == "supported entrypoint inventory differs from contract"
    ]

    assert len(route_errors) == 1
    assert "polisyos.fixture.api" in route_errors[0]["detail"]
    assert package["module"] == "polisyos.fixture"
    assert report["public_surface_inventory_evidence"]["complete_verdict"] is True
    assert report["public_surface_inventory_evidence"]["predicate_status"] == "mismatch"


def test_phase5_10_public_surface_route_rows_must_match_declared_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_public_surface_inventory_fixture(tmp_path)
    inventory_path = tmp_path / "architecture/public_surface/inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    package = inventory["packages"][0]
    package["entrypoints"][1]["module"] = "polisyos.fixture.hidden"
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    report = _run_public_surface_report(tmp_path, monkeypatch)
    route_errors = [
        error
        for error in report["contract_errors"]
        if error["message"] == "supported entrypoint inventory differs from contract"
    ]

    assert len(route_errors) == 1
    assert "polisyos.fixture.hidden" in route_errors[0]["detail"]
    assert report["public_surface_inventory_evidence"]["predicate_status"] == "mismatch"


def test_phase5_10_public_surface_rejects_extra_package_and_family_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_public_surface_inventory_fixture(tmp_path)
    inventory_path = tmp_path / "architecture/public_surface/inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    extra_package = dict(inventory["packages"][0])
    extra_package["module"] = "polisyos.fixture.extra"
    inventory["packages"].append(extra_package)
    inventory["generated_artifact_families"][0]["outputs"] = ["architecture/changed.json"]
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    report = _run_public_surface_report(tmp_path, monkeypatch)
    messages = {error["message"] for error in report["contract_errors"]}

    assert "inventory has package rows outside the contract" in messages
    assert "generated-artifact family inventory differs from contract" in messages
    assert report["public_surface_inventory_evidence"]["predicate_status"] == "mismatch"

    inventory["generated_artifact_families"] = []
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    missing_family_report = _run_public_surface_report(tmp_path, monkeypatch)
    family_error = next(
        error
        for error in missing_family_report["contract_errors"]
        if error["message"] == "generated-artifact family inventory differs from contract"
    )
    assert "fixture-family" in family_error["detail"]


def test_phase5_10_public_surface_malformed_route_rows_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_public_surface_inventory_fixture(tmp_path)
    inventory_path = tmp_path / "architecture/public_surface/inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["packages"][0]["entrypoints"] = [None]
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    report = _run_public_surface_report(tmp_path, monkeypatch)
    evidence = report["public_surface_inventory_evidence"]

    assert report["contract_errors"]
    assert evidence["complete_verdict"] is False
    assert evidence["predicate_status"] == "not_established"


@pytest.mark.parametrize(
    ("contract_field", "inventory_field"),
    list(gates._canonical_public_surface_context()[1].items()),
)
def test_phase5_10_public_surface_schema_field_removal_fails_closed_with_markers(
    contract_field: str,
    inventory_field: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_public_surface_inventory_fixture(tmp_path)
    contract_path = tmp_path / "architecture/public_surface/contract.toml"
    inventory_path = tmp_path / "architecture/public_surface/inventory.json"
    contract_text = contract_path.read_text(encoding="utf-8")
    if contract_field == "notes":
        contract_text = contract_text.replace(
            "major_subsystem = false\n",
            'major_subsystem = false\nnotes = "Fixture note."\n',
        )
    contract_line_prefix = f"{contract_field} = "
    contract_text = (
        "\n".join(
            line for line in contract_text.splitlines() if not line.startswith(contract_line_prefix)
        )
        + "\n"
    )
    contract_path.write_text(contract_text, encoding="utf-8")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory_package = inventory["packages"][0]
    inventory_package.pop(inventory_field, None)
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    report = _run_public_surface_report(tmp_path, monkeypatch)
    evidence = report["public_surface_inventory_evidence"]

    assert (
        inventory_package.get("module") == "polisyos.fixture"
        or inventory_package.get("classification") == "public_stable"
    )
    assert evidence["complete_verdict"] is False
    assert evidence["predicate_status"] == "not_established"
    assert report["contract_errors"]


def _canonical_inventory_schema_fields() -> list[tuple[str, str]]:
    _, _, schema = gates._canonical_public_surface_context()
    package = schema["packages"][0]
    entrypoint = package["entrypoints"][0]
    family = schema["generated_artifact_families"][0]
    return [
        *(("root", name) for name in schema),
        *(("package", name) for name in package),
        *(("entrypoint", name) for name in entrypoint),
        *(("family", name) for name in family),
    ]


@pytest.mark.parametrize(
    ("row_kind", "field_name"),
    _canonical_inventory_schema_fields(),
)
def test_phase5_10_public_surface_all_canonical_inventory_fields_are_required(
    row_kind: str,
    field_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_public_surface_inventory_fixture(tmp_path)
    inventory_path = tmp_path / "architecture/public_surface/inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if row_kind == "root":
        inventory.pop(field_name)
    elif row_kind == "package":
        inventory["packages"][0].pop(field_name)
    elif row_kind == "entrypoint":
        inventory["packages"][0]["entrypoints"][0].pop(field_name)
    else:
        inventory["generated_artifact_families"][0].pop(field_name)
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    report = _run_public_surface_report(tmp_path, monkeypatch)
    evidence = report["public_surface_inventory_evidence"]

    assert report["contract_errors"]
    assert evidence["complete_verdict"] is False
    assert evidence["predicate_status"] == "not_established"
    packages = inventory.get("packages", [])
    if packages:
        assert (
            packages[0].get("module") == "polisyos.fixture"
            or packages[0].get("classification") == "public_stable"
        )


def test_phase5_10_public_surface_notes_drift_fails_with_package_markers_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_public_surface_inventory_fixture(tmp_path)
    inventory_path = tmp_path / "architecture/public_surface/inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["packages"][0]["notes"] = "changed while package identity is retained"
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    report = _run_public_surface_report(tmp_path, monkeypatch)
    notes_errors = [
        error
        for error in report["contract_errors"]
        if error["subject"] == "polisyos.fixture" and error["message"] == "notes drift"
    ]

    assert inventory["packages"][0]["module"] == "polisyos.fixture"
    assert inventory["packages"][0]["classification"] == "public_stable"
    assert len(notes_errors) == 1
    assert report["public_surface_inventory_evidence"]["complete_verdict"] is True
    assert report["public_surface_inventory_evidence"]["predicate_status"] == "mismatch"
