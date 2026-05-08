from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase3_6_dead_override_gate_is_registered_report_only() -> None:
    gates_payload = _read_toml(REPO_ROOT / "architecture" / "gates" / "report_only.toml")
    gates = {gate["id"]: gate for gate in gates_payload["gate"]}
    gate = gates["dead-static-analysis-overrides"]

    assert gate["mode"] == "report_only"
    assert gate["owner"] == "team-devx"
    assert gate["command"] == "uv run python tools/ops_runners/reports/dead_overrides.py"
    assert gate["source_contracts"] == [
        "architecture/tooling/static_analysis_overrides.toml",
        "architecture/tooling/tool_config_split.toml",
        "architecture/tooling/mypy/generated.ini",
        "architecture/tooling/ruff/generated.toml",
        "mypy.ini",
        "ruff.toml",
    ]

    static = _read_toml(REPO_ROOT / "architecture" / "tooling" / "static_analysis_overrides.toml")
    phase_gate = static["phase_3_6_dead_override_gate"]
    assert phase_gate["status"] == "report_only"
    assert phase_gate["required_exception_metadata"] == [
        "owner",
        "sunset_or_permanent_rationale",
    ]
    split = static["tool_config_split"]
    assert split["check_command"] == "uv run polisyos-tools workspace tool-configs --check"
    assert split["mypy_config"] == "architecture/tooling/mypy/generated.ini"
    assert split["ruff_config"] == "architecture/tooling/ruff/generated.toml"


def _read_toml(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))
