#!/usr/bin/env python3
"""Validate the sound DS5 enforcement core."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from textwrap import dedent
from typing import Any

ATLAS_DIR = Path(__file__).resolve().parent
STATUS_CHECKER_PATH = ATLAS_DIR / "check_status_retirement_inventory.py"
DISPOSITION_CHECKER_PATH = ATLAS_DIR / "check_frontend_disposition_register.py"

_SPEC = importlib.util.spec_from_file_location(
    "status_retirement_checker", STATUS_CHECKER_PATH
)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to import status checker from {STATUS_CHECKER_PATH}")
status_checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(status_checker)

_DISPOSITION_SPEC = importlib.util.spec_from_file_location(
    "atlas_enforcement_disposition_checker", DISPOSITION_CHECKER_PATH
)
if _DISPOSITION_SPEC is None or _DISPOSITION_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(
        f"Unable to import disposition checker from {DISPOSITION_CHECKER_PATH}"
    )
disposition_checker = importlib.util.module_from_spec(_DISPOSITION_SPEC)
_DISPOSITION_SPEC.loader.exec_module(disposition_checker)


def _override_diagnostic_errors(scan: Mapping[str, Any]) -> list[str]:
    """Translate TypeScript diagnostics from synthetic witnesses."""
    return sorted(
        {
            "invalid_source_override:"
            + str(diagnostic.get("path", "unknown"))
            + ":"
            + str(diagnostic.get("line", 0))
            + ":TS"
            + str(diagnostic.get("code", "unknown"))
            for diagnostic in scan.get("overrideDiagnostics", [])
            if isinstance(diagnostic, Mapping)
        }
    )


def _generated_owner_receipt(inventory: Mapping[str, Any]) -> dict[str, str]:
    """Project the content-bound generated-client receipt used by the scan."""
    generated = inventory["sources"]["generated_client"]
    return {
        key: str(generated[key])
        for key in (
            "canonical_path",
            "types_path",
            "canonical_sha256",
            "types_sha256",
        )
    }


def validate_enforcement(
    *, source_overrides: Mapping[str, str] | None = None
) -> tuple[list[str], dict[str, Any]]:
    """Validate the governed DS4 bridge and declaration-level DS5 census."""
    inventory = status_checker._load_json(status_checker.INVENTORY_PATH)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    scan = status_checker._scan(
        source_overrides,
        inventory=inventory,
        validate_override_diagnostics=source_overrides is not None,
        authority_prop_descriptors=(
            disposition_checker._authority_prop_descriptors()
            if source_overrides is None
            else ()
        ),
    )
    scan["generatedOwnerReceipt"] = _generated_owner_receipt(inventory)
    errors = _override_diagnostic_errors(scan)
    if source_overrides is None:
        errors.extend(
            status_checker.validate_inventory(inventory, debt, live_probes=True)
        )
        disposition = disposition_checker._load_json(
            disposition_checker.REGISTER_PATH
        )
        errors.extend(
            disposition_checker._authority_presentation_errors(
                disposition,
                live_probes=True,
                scan=scan,
            )
        )
    return sorted(set(errors)), scan


def _corruption_probes() -> list[str]:
    """Return labels for retained-core properties that a corruption escaped."""
    escaped: list[str] = []
    package_path = "packages/atlas-ui/src/index.ts"
    probe_path = (
        "apps/runtime-dashboard/src/shared/lib/domain/"
        "packageOwnerCorruptionProbe.tsx"
    )
    exports = dedent(
        """
        export { AuthorityBadge } from "./primitives/AuthorityBadge";
        export type { AuthorityPresentation } from "./primitives/AuthorityBadge";
        export { Button } from "./primitives/Button";
        """
    ).strip() + "\n"

    errors, scan = validate_enforcement(
        source_overrides={
            package_path: exports,
            probe_path: dedent(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const props: { presentation?: Atlas.AuthorityPresentation } = {};
                export const Probe = () => <Atlas.AuthorityBadge {...props} />;
                """
            ).strip()
            + "\n",
        }
    )
    if (
        [item.get("code") for item in scan.get("overrideDiagnostics", [])]
        != [2322]
        or not any(error.endswith(":TS2322") for error in errors)
    ):
        escaped.append("override-diagnostics")

    errors, scan = validate_enforcement(
        source_overrides={
            package_path: exports,
            probe_path: dedent(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                function LocalControl({ disabled: _disabled }: { disabled?: boolean }) {
                  return <div />;
                }
                const presentation = {} as Atlas.AuthorityPresentation;
                export const Probe = () => <>
                  <Atlas.AuthorityBadge presentation={presentation} />
                  <Atlas.Button disabled>Review</Atlas.Button>
                  <LocalControl disabled />
                </>;
                """
            ).strip()
            + "\n",
        }
    )
    pairs = {
        (row.get("componentDeclarationPath"), row.get("prop"))
        for row in scan.get("authoritySinkDeclarations", [])
        if isinstance(row, Mapping)
    }
    if errors or (
        "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
        "presentation",
    ) not in pairs or (
        "packages/atlas-ui/src/primitives/Button.tsx",
        "disabled",
    ) not in pairs or any("packageOwnerCorruptionProbe" in str(path) for path, _ in pairs):
        escaped.append("real-atlas-declaration-census")

    inventory = status_checker._load_json(status_checker.INVENTORY_PATH)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    corrupted = copy.deepcopy(inventory)
    corrupted["sources"]["generated_client"]["canonical_sha256"] = "sha256:" + "0" * 64
    expected = (
        "inventory_source_hash_drift:"
        + inventory["sources"]["generated_client"]["canonical_path"]
    )
    if expected not in status_checker.validate_inventory(
        corrupted, debt, live_probes=False
    ):
        escaped.append("generated-owner-content-binding")
    return escaped


def _summary(scan: Mapping[str, Any]) -> dict[str, Any]:
    inventory = status_checker._load_json(status_checker.INVENTORY_PATH)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    status_summary = status_checker._summary(inventory, debt)
    denominators = scan.get("sourceDenominators", {})
    return {
        "atlas_ui_production_sources": denominators.get("atlasUiProduction"),
        "authority_sink_declarations": len(
            scan.get("authoritySinkDeclarations", [])
        ),
        "authority_badge_sites": len(scan.get("badgeSites", [])),
        "authority_prop_groups": len(scan.get("authorityPropCensus", [])),
        "current_authored_statuses": status_summary["current_authored"],
        "ds1_status_rows": status_summary["ds1_rows"],
        "semantic_retirement_debt": status_summary["semantic_retirement_debt"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the retained-core checker and optional corruption witnesses."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--corruption-probes", action="store_true")
    args = parser.parse_args(argv)
    errors, scan = validate_enforcement()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.corruption_probes:
        escaped = _corruption_probes()
        if escaped:
            print("corruption probes escaped: " + ", ".join(escaped), file=sys.stderr)
            return 1
        print("Atlas enforcement corruption probes: PASS")
    print(json.dumps(_summary(scan), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
