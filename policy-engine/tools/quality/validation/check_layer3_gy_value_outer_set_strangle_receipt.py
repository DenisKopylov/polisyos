#!/usr/bin/env python3
"""Validate the GY-N-V strangle receipt for S1 household value bounds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

OUTPUT_PATH = (
    "architecture/policy_design_case/layer3_gy_value_outer_set_strangle_receipt.json"
)
SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.value_outer_set_strangle_receipt.v1"

_OLD_FIELD_NAMES = (
    "disposable_income_lower",
    "disposable_income_upper",
    "poverty_rate_lower",
    "poverty_rate_upper",
    "transfer_intensity_lower",
    "transfer_intensity_upper",
    "identification_mode_code",
)
_PROTECTED_SOURCE_PATHS = (
    "src/polisyos/foundry/contracts/state.py",
    "src/polisyos/foundry/agent_sim/wiring/executors.py",
    "src/polisyos/ir/kernel/slots.py",
)


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_live_payload(repo_root: Path | None = None) -> dict[str, Any]:
    """Recompute the strangle receipt from the live state, slots, and S1 payload."""

    repo_root = (repo_root or _default_repo_root()).resolve()
    _ensure_src_path(repo_root)

    from polisyos.foundry.contracts.state import HouseholdCellState
    from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY
    from polisyos.runtime.quality.data_state_substrate import (
        L5FamilyAuthority,
        L5FamilyBindingProfile,
        _household_payload,
    )

    household_state = HouseholdCellState.empty(1)
    state_remaining = [
        field_name for field_name in _OLD_FIELD_NAMES if hasattr(household_state, field_name)
    ]
    slot_remaining = [
        slot_id
        for slot_id in DEFAULT_SLOT_REGISTRY.slots
        if any(field_name in slot_id for field_name in _OLD_FIELD_NAMES)
    ]
    source_remaining = _source_remaining_callers(repo_root)

    authority = L5FamilyAuthority(
        family_id="household_distribution",
        coverage_score=1.0,
        trust_tier="authoritative_partial_coverage",
        trust_cap=0.85,
        trust_multiplier=0.95,
        min_coverage=0.5,
        max_coverage=1.0,
        promotion_floor=0.5,
        identification_mode="proxy_identified",
        value_authority="proxy_bounds",
        measurement_registry_ref=(
            "repo://production_data/l5/measurement_registry.json#/coverage_rules/"
            "household_distribution"
        ),
        identification_registry_ref=(
            "repo://production_data/l5/identification_mode_registry.json#/"
            "household_distribution"
        ),
    )
    profile = L5FamilyBindingProfile(
        period_start="2022-03",
        period_end="2022-03",
        schema_regime_status="single_regime",
        regime_ids=("ukraine_schema_v2",),
        boundary_buffer_periods=1,
        families=(authority,),
    )
    payload = _household_payload(
        (
            (
                0,
                "UA",
                100.0,
                10.0,
                False,
                0.5,
                80.0,
                120.0,
            ),
        ),
        authority,
        l5_profile=profile,
        world_model_record_ref="gy-n3:world-preimage:strangle-receipt-probe",
    )
    payload_remaining = [
        key for key in payload if any(field_name == key for field_name in _OLD_FIELD_NAMES)
    ]
    value_outer_set_present = "value_outer_set" in payload
    remaining_callers = [
        *[f"HouseholdCellState.{field_name}" for field_name in state_remaining],
        *[f"slot:{slot_id}" for slot_id in slot_remaining],
        *source_remaining,
        *[f"s1_payload:{key}" for key in payload_remaining],
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "strangle_receipt": {
            "receipt_id": "layer3-gy-value-outer-set-household-bounds-strangle",
            "pattern_id": "P28",
            "predecessor_ref": "foundry.contracts.state.HouseholdCellState.ad_hoc_household_bounds",
            "replacement_ref": "core.contracts.runtime.ValueOuterSet",
            "disposition": "deleted",
            "remaining_callers": remaining_callers,
            "removed_loc": [
                f"src/polisyos/foundry/contracts/state.py:HouseholdCellState.{field_name}"
                for field_name in _OLD_FIELD_NAMES
            ],
            "verified_by": [
                "tools/quality/validation/check_layer3_gy_value_outer_set_strangle_receipt.py --check",
                "tests/unit/foundry/contracts/test_state_contracts.py",
                "tests/unit/foundry/data_plane/test_bindings_multiscale.py",
                "tests/unit/foundry/agent_sim/test_wiring.py",
                "tests/integration/runtime_quality/test_data_state_substrate.py",
            ],
            "value_outer_set_present": value_outer_set_present,
            "guard_status": (
                "pass" if not remaining_callers and value_outer_set_present else "fail"
            ),
        },
    }


def validate(repo_root: Path) -> dict[str, Any]:
    """Validate the committed receipt against live deletion checks."""

    path = repo_root / OUTPUT_PATH
    issues: list[dict[str, Any]] = []
    live = build_live_payload(repo_root)
    receipt = live["strangle_receipt"]
    if receipt["remaining_callers"]:
        issues.append(
            {
                "code": "value_outer_set_strangle_remaining_callers",
                "remaining_callers": receipt["remaining_callers"],
            }
        )
    if receipt["guard_status"] != "pass":
        issues.append({"code": "value_outer_set_strangle_guard_failed"})
    if not path.is_file():
        issues.append({"code": "value_outer_set_strangle_receipt_missing", "path": OUTPUT_PATH})
    else:
        committed = json.loads(path.read_text(encoding="utf-8"))
        if committed != live:
            issues.append({"code": "value_outer_set_strangle_receipt_drift", "path": OUTPUT_PATH})
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
    }


def write(repo_root: Path) -> None:
    """Write the live strangle receipt artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_live_payload(repo_root), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _source_remaining_callers(repo_root: Path) -> list[str]:
    remaining: list[str] = []
    for relative in _PROTECTED_SOURCE_PATHS:
        path = repo_root / relative
        if not path.is_file():
            remaining.append(f"missing_source:{relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for field_name in _OLD_FIELD_NAMES:
            if field_name in text:
                remaining.append(f"{relative}:{field_name}")
    return remaining


def _ensure_src_path(repo_root: Path) -> None:
    for path in (repo_root, repo_root / "src"):
        value = path.as_posix()
        if value not in sys.path:
            sys.path.insert(0, value)


def main(argv: list[str] | None = None) -> int:
    """Run the strangle receipt validator."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    if args.write:
        write(repo_root)
    report = validate(repo_root)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "pass":
        for issue in report["issues"]:
            print(f"{issue.get('code')}: {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    from tools.lib.timing import run_timed_entrypoint

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
