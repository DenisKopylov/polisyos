from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

from tools.quality.validation import check_debt_ledger, check_package_import_gates

REPO_ROOT = Path(__file__).resolve().parents[3]
CONCERN_CONTRACT = REPO_ROOT / "architecture" / "policies" / "cross_cutting_concerns.toml"
PUBLIC_SURFACE_CONTRACT = REPO_ROOT / "architecture" / "public_surface" / "contract.toml"
PACKAGE_CONTRACT_ROOT = REPO_ROOT / "architecture" / "packages"
SOURCE_ROOT = REPO_ROOT / "src" / "polisyos"
DEBT_REGISTER = REPO_ROOT / "docs" / "plans" / "active" / "DEBT-REGISTER.md"
NAME_REGISTRY = REPO_ROOT / "architecture" / "name_registry.toml"
ADR_INDEX = REPO_ROOT / "docs" / "adr" / "index.toml"
ADR_0148 = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "repository-structure-0148-cross-cutting-concern-canonical-homes.md"
)

REQUIRED_PHASE_1_5_CONCERNS = {
    "observability",
    "security",
    "registry",
    "discovery",
    "configuration",
    "tracing",
    "calibration",
}
DEFERRED_PUBLIC_CANONICAL_INTERFACES = {
    "polisyos.core.observability": "core-observability-canonical-interface-contract-drift",
}
ACTIVE_DEFERRED_DEBT_STATUSES = frozenset({"open", "open_unmerged", "blocked"})
TOUCHED_PUBLIC_SURFACE_MODULES = frozenset({"polisyos.common", "polisyos.core"})


def _load_toml(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _public_canonical_interfaces() -> set[str]:
    contract = _load_toml(CONCERN_CONTRACT)
    return {
        str(concern["canonical_interface"])
        for concern in contract["concern"]
        if concern.get("public_status") == "public"
    }


def _supported_entrypoints_by_module() -> dict[str, set[str]]:
    contract = _load_toml(PUBLIC_SURFACE_CONTRACT)
    return {
        str(package["module"]): {
            str(entrypoint) for entrypoint in package["supported_entrypoints"]
        }
        for package in contract["package"]
    }


def _primary_supported_entrypoints_by_module() -> dict[str, set[str]]:
    entrypoints: dict[str, set[str]] = {}
    for path in sorted(PACKAGE_CONTRACT_ROOT.glob("*.toml")):
        contract = _load_toml(path)
        package = contract.get("package")
        if not isinstance(package, dict) or package.get("primary_contract") is not True:
            continue
        entrypoints[str(package["module"])] = {
            str(entrypoint)
            for entrypoint in contract.get("public_surface", {}).get(
                "supported_entrypoints", []
            )
        }
    return entrypoints


def _registered_debt_statuses() -> dict[str, str]:
    debts, _ = check_debt_ledger._parse_register(DEBT_REGISTER.read_text(encoding="utf-8"))
    return {str(debt.debt_id): str(debt.status) for debt in debts}


def _cross_package_deep_imports(interfaces: set[str]) -> list[str]:
    violations: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        source_root = path.relative_to(SOURCE_ROOT).parts[0]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                targets.append(node.module)
            else:
                continue
            for interface in interfaces:
                owner_root = interface.split(".")[1]
                if source_root == owner_root:
                    continue
                if any(target.startswith(f"{interface}.") for target in targets):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno} -> {interface}.*"
                    )
                    break
    return violations


def test_phase1_5_public_canonical_interfaces_are_supported_or_registered_deferred() -> None:
    public_interfaces = _public_canonical_interfaces()
    supported_by_module = _supported_entrypoints_by_module()
    primary_supported_by_module = _primary_supported_entrypoints_by_module()
    supported_entrypoints = set().union(*supported_by_module.values())
    primary_supported_entrypoints = set().union(*primary_supported_by_module.values())
    deferred_interfaces = set(DEFERRED_PUBLIC_CANONICAL_INTERFACES)
    debt_statuses = _registered_debt_statuses()
    inactive_debts = {
        debt_id: debt_statuses.get(debt_id)
        for debt_id in DEFERRED_PUBLIC_CANONICAL_INTERFACES.values()
        if debt_statuses.get(debt_id) not in ACTIVE_DEFERRED_DEBT_STATUSES
    }

    assert deferred_interfaces <= public_interfaces
    assert inactive_debts == {}
    assert public_interfaces - supported_entrypoints == deferred_interfaces
    assert public_interfaces - primary_supported_entrypoints == deferred_interfaces
    assert {
        module: primary_supported_by_module.get(module, set())
        for module in TOUCHED_PUBLIC_SURFACE_MODULES
    } == {
        module: supported_by_module.get(module, set())
        for module in TOUCHED_PUBLIC_SURFACE_MODULES
    }


@pytest.mark.parametrize("terminal_status", ["closed", "folded"])
def test_phase1_5_terminal_debt_cannot_authorize_deferred_interface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal_status: str,
) -> None:
    register = tmp_path / "DEBT-REGISTER.md"
    register.write_text(
        "\n".join(
            [
                "## A. Test debts",
                "",
                "| id | subject | owner | status | closure signal |",
                "| --- | --- | --- | --- | --- |",
                "| `core-observability-canonical-interface-contract-drift` "
                f"| test | team-observability | `{terminal_status}` | test |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tests.repo_quality.architecture.test_last_mile_cross_cutting_concerns.DEBT_REGISTER",
        register,
    )

    with pytest.raises(AssertionError):
        test_phase1_5_public_canonical_interfaces_are_supported_or_registered_deferred()


def test_phase1_5_primary_surface_entrypoints_are_owner_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = tmp_path / "packages"
    package_root.mkdir()
    for source in PACKAGE_CONTRACT_ROOT.glob("*.toml"):
        text = source.read_text(encoding="utf-8")
        if source.name == "common.toml":
            text = text.replace("polisyos.common.config", "polisyos.core.security")
        elif source.name == "core.toml":
            text = text.replace("polisyos.core.security", "polisyos.common.config")
        (package_root / source.name).write_text(text, encoding="utf-8")
    monkeypatch.setattr(
        "tests.repo_quality.architecture.test_last_mile_cross_cutting_concerns.PACKAGE_CONTRACT_ROOT",
        package_root,
    )

    with pytest.raises(AssertionError):
        test_phase1_5_public_canonical_interfaces_are_supported_or_registered_deferred()


def test_phase1_5_closed_public_canonical_interfaces_use_exact_facades() -> None:
    closed_interfaces = _public_canonical_interfaces() - set(DEFERRED_PUBLIC_CANONICAL_INTERFACES)

    assert _cross_package_deep_imports(closed_interfaces) == []


def _write_contract(
    tmp_path: Path,
    *,
    extra_exceptions: list[str] | None = None,
) -> None:
    architecture = tmp_path / "architecture"
    architecture.mkdir(parents=True, exist_ok=True)
    (architecture / "policies").mkdir(exist_ok=True)
    exception_lines = extra_exceptions or []
    (architecture / "policies" / "cross_cutting_concerns.toml").write_text(
        "\n".join(
            [
                "[cross_cutting_concerns]",
                'status = "fail_closed"',
                "",
                "[canonical_home_contract]",
                'phase = "repository-best-in-class-last-mile-phase-1.5"',
                'adr = "docs/adr/repository-structure-0148-cross-cutting-concern-canonical-homes.md"',
                "fail_closed = true",
                'adapter_module_pattern = "polisyos.<package>._adapters.<concern>"',
                'blocked_file_names = ["observability", "security", "registry", "discovery", "configuration", "config", "tracing", "trace", "calibration"]',
                "",
                "[[concern]]",
                'name = "observability"',
                'canonical_home = "polisyos.core.observability"',
                'canonical_interface = "polisyos.core.observability"',
                'canonical_owner = "team-observability"',
                'decision = "canonical_interface_plus_package_adapters"',
                'public_status = "public"',
                'semantic_axis = "telemetry primitives"',
                'import_rule = "shared telemetry imports use polisyos.core.observability"',
                'adapter_policy = "package adapters import the canonical home"',
                'sunset = "none"',
                'file_names = ["observability"]',
                'allowed_adapters = []',
                'unresolved_collisions = []',
                "",
                "[[concern]]",
                'name = "registry"',
                'canonical_home = "polisyos.core.registry"',
                'canonical_interface = "polisyos.core.registry"',
                'canonical_owner = "team-core"',
                'decision = "canonical_interface_plus_package_adapters"',
                'public_status = "public"',
                'semantic_axis = "registry primitives"',
                'import_rule = "shared registry imports use polisyos.core.registry"',
                'adapter_policy = "package adapters import the canonical home"',
                'sunset = "none"',
                'file_names = ["registry"]',
                'allowed_adapters = []',
                'unresolved_collisions = []',
                *exception_lines,
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_phase1_5_contract_has_required_canonical_home_decisions_and_adr() -> None:
    contract = _load_toml(CONCERN_CONTRACT)
    registry = _load_toml(NAME_REGISTRY)
    index = _load_toml(ADR_INDEX)
    concerns = {entry["name"]: entry for entry in contract["concern"]}
    registry_decisions = {
        entry["name"]: entry
        for entry in registry.get("phase1_5_cross_cutting_concern_decision", [])
    }
    adr_rows = {entry["id"]: entry for entry in index["adr"]}

    assert ADR_0148.exists()
    assert contract["canonical_home_contract"]["fail_closed"] is True
    assert (
        contract["canonical_home_contract"]["adr"]
        == "docs/adr/repository-structure-0148-cross-cutting-concern-canonical-homes.md"
    )
    assert set(concerns) >= REQUIRED_PHASE_1_5_CONCERNS
    assert set(registry_decisions) >= REQUIRED_PHASE_1_5_CONCERNS
    assert "RSR-0148" in adr_rows

    for name in REQUIRED_PHASE_1_5_CONCERNS:
        concern = concerns[name]
        decision = registry_decisions[name]
        assert concern["canonical_home"] or concern.get("scoped_ok") is True
        assert decision["decision"] in {"canonical_home_with_adapters", "scoped_ok"}
        assert decision["owner"]
        assert decision["rationale"]


def test_phase1_5_non_canonical_root_concern_file_fails(tmp_path: Path) -> None:
    _write_contract(tmp_path)
    package_root = tmp_path / "src" / "polisyos" / "fabric"
    package_root.mkdir(parents=True)
    (package_root / "observability.py").write_text("VALUE = 1\n", encoding="utf-8")

    findings = check_package_import_gates._check_cross_cutting_concern_homes(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "cross-cutting-concern-home",
            "src/polisyos/fabric/observability.py",
            "cross-cutting concern root is outside its canonical home and lacks "
            "a scoped exception",
            "concern=observability canonical_home=polisyos.core.observability",
        )
    ]


def test_phase1_5_duplicate_concern_package_without_exception_fails(tmp_path: Path) -> None:
    _write_contract(tmp_path)
    package_root = tmp_path / "src" / "polisyos" / "ir" / "registry"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")

    findings = check_package_import_gates._check_cross_cutting_concern_homes(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "cross-cutting-concern-home",
            "src/polisyos/ir/registry",
            "cross-cutting concern package is outside its canonical home and lacks "
            "a scoped exception",
            "concern=registry canonical_home=polisyos.core.registry",
        )
    ]


def test_phase1_5_group_level_concern_file_requires_scoped_exception(
    tmp_path: Path,
) -> None:
    _write_contract(tmp_path)
    group_file = tmp_path / "src" / "polisyos" / "fabric" / "connectors" / "registry.py"
    group_file.parent.mkdir(parents=True)
    group_file.write_text("VALUE = 1\n", encoding="utf-8")

    findings = check_package_import_gates._check_cross_cutting_concern_homes(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "cross-cutting-concern-home",
            "src/polisyos/fabric/connectors/registry.py",
            "group-level cross-cutting concern file must live under "
            "<package>/_adapters/<concern>.py or carry a scoped exception",
            "concern=registry canonical_home=polisyos.core.registry",
        )
    ]


def test_phase1_5_scoped_exception_needs_owner_rationale_and_sunset(
    tmp_path: Path,
) -> None:
    _write_contract(
        tmp_path,
        extra_exceptions=[
            "",
            "[[scoped_exception]]",
            'concern = "registry"',
            'path = "src/polisyos/fabric/connectors/registry.py"',
            'owner = "team-fabric"',
            'rationale = ""',
            'sunset = ""',
        ],
    )
    group_file = tmp_path / "src" / "polisyos" / "fabric" / "connectors" / "registry.py"
    group_file.parent.mkdir(parents=True)
    group_file.write_text("VALUE = 1\n", encoding="utf-8")

    findings = check_package_import_gates._check_cross_cutting_concern_homes(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "cross-cutting-concern-home",
            "src/polisyos/fabric/connectors/registry.py",
            "scoped cross-cutting concern exception missing `rationale`",
        ),
        check_package_import_gates.Finding(
            "cross-cutting-concern-home",
            "src/polisyos/fabric/connectors/registry.py",
            "scoped cross-cutting concern exception missing `sunset`",
        ),
    ]


def test_phase1_5_adapter_file_must_import_canonical_home(tmp_path: Path) -> None:
    _write_contract(tmp_path)
    adapter_file = tmp_path / "src" / "polisyos" / "fabric" / "_adapters" / "registry.py"
    adapter_file.parent.mkdir(parents=True)
    adapter_file.write_text("VALUE = 1\n", encoding="utf-8")

    findings = check_package_import_gates._check_cross_cutting_concern_homes(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "cross-cutting-concern-adapter",
            "src/polisyos/fabric/_adapters/registry.py",
            "cross-cutting concern adapter must import its canonical home",
            "concern=registry canonical_home=polisyos.core.registry",
        )
    ]

    adapter_file.write_text(
        "from polisyos.core.registry import RegistryProtocol\n",
        encoding="utf-8",
    )

    assert check_package_import_gates._check_cross_cutting_concern_homes(tmp_path) == []
