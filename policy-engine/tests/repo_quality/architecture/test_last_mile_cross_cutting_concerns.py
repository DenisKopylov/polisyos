from __future__ import annotations

import tomllib
from pathlib import Path

from tools.quality.validation import check_package_import_gates

REPO_ROOT = Path(__file__).resolve().parents[3]
CONCERN_CONTRACT = REPO_ROOT / "architecture" / "policies" / "cross_cutting_concerns.toml"
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


def _load_toml(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


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
    assert REQUIRED_PHASE_1_5_CONCERNS <= set(concerns)
    assert REQUIRED_PHASE_1_5_CONCERNS <= set(registry_decisions)
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
