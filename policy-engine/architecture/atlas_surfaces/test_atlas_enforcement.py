"""Behavioral tests for the retained DS5 enforcement core."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from textwrap import dedent
from typing import Any

ATLAS_DIR = Path(__file__).resolve().parent
ENFORCEMENT_CHECKER_PATH = ATLAS_DIR / "check_atlas_enforcement.py"

_SPEC = importlib.util.spec_from_file_location(
    "atlas_enforcement_checker", ENFORCEMENT_CHECKER_PATH
)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(
        f"Unable to import enforcement checker from {ENFORCEMENT_CHECKER_PATH}"
    )
checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(checker)

PACKAGE_PATH = "packages/atlas-ui/src/index.ts"
PROBE_PATH = "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerProbe.tsx"
ATLAS_EXPORTS = (
    'export { AuthorityBadge } from "./primitives/AuthorityBadge";\n'
    'export type { AuthorityPresentation } from '
    '"./primitives/AuthorityBadge";\n'
    'export { Button } from "./primitives/Button";\n'
    'export { SegmentedControl } from "./primitives/SegmentedControl";\n'
)


def ts_source(source: str) -> str:
    """Return a line-stable TypeScript override fixture."""
    return dedent(source).strip() + "\n"


class AtlasEnforcementTests(unittest.TestCase):
    """Prove the retained checker states only decidable local guarantees."""

    def _validate(
        self,
        package_source: str,
        probe_source: str,
    ) -> tuple[list[str], dict[str, Any]]:
        return checker.validate_enforcement(
            source_overrides={
                PACKAGE_PATH: package_source,
                PROBE_PATH: probe_source,
            }
        )

    def test_enforcement_scan_exposes_only_retained_local_facts(self) -> None:
        errors, scan = self._validate(
            ATLAS_EXPORTS,
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const presentation = {} as Atlas.AuthorityPresentation;
                export const Probe = () =>
                  <Atlas.AuthorityBadge presentation={presentation} />;
                """
            ),
        )

        self.assertEqual([], errors)
        self.assertNotIn("unauthorizedStatusOwners", scan)
        self.assertNotIn("unauthorizedStatusSinks", scan)
        self.assertIn("authoritySinkDeclarations", scan)

    def test_authority_sink_census_resolves_real_atlas_prop_declarations(
        self,
    ) -> None:
        errors, scan = self._validate(
            ATLAS_EXPORTS,
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                function LocalControl({ disabled: _disabled }: {
                  disabled?: boolean;
                }) {
                  return <div />;
                }
                const presentation = {} as Atlas.AuthorityPresentation;
                export function Probe() {
                  return <>
                    <Atlas.AuthorityBadge presentation={presentation} />
                    <Atlas.Button disabled>Review</Atlas.Button>
                    <Atlas.SegmentedControl
                      value="a"
                      options={[{ value: "a", label: "A" }]}
                      onValueChange={() => undefined}
                      disabled
                    />
                    <LocalControl disabled />
                  </>;
                }
                """
            ),
        )

        self.assertEqual([], errors)
        pairs = {
            (row["componentDeclarationPath"], row["prop"])
            for row in scan["authoritySinkDeclarations"]
        }
        self.assertIn(
            (
                "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
                "presentation",
            ),
            pairs,
        )
        self.assertIn(
            ("packages/atlas-ui/src/primitives/Button.tsx", "disabled"),
            pairs,
        )
        self.assertIn(
            (
                "packages/atlas-ui/src/primitives/SegmentedControl.tsx",
                "disabled",
            ),
            pairs,
        )
        self.assertFalse(
            any("packageOwnerProbe" in path for path, _prop in pairs)
        )

    def test_authority_sink_census_does_not_invent_absent_props(self) -> None:
        errors, scan = self._validate(
            ATLAS_EXPORTS,
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                export const Probe = () => <Atlas.Button>Review</Atlas.Button>;
                """
            ),
        )

        self.assertEqual([], errors)
        self.assertFalse(
            any(
                row["componentDeclarationPath"].endswith("/Button.tsx")
                for row in scan["authoritySinkDeclarations"]
            )
        )

    def test_generated_owner_receipt_and_status_bridge_are_content_bound(
        self,
    ) -> None:
        errors, scan = checker.validate_enforcement()
        inventory = checker.status_checker._load_json(
            checker.status_checker.INVENTORY_PATH
        )
        generated = inventory["sources"]["generated_client"]

        self.assertEqual([], errors)
        self.assertEqual(
            {
                key: generated[key]
                for key in (
                    "canonical_path",
                    "types_path",
                    "canonical_sha256",
                    "types_sha256",
                )
            },
            scan["generatedOwnerReceipt"],
        )
        self.assertEqual(
            {
                "current_authored_statuses": 15,
                "ds1_status_rows": 47,
                "semantic_retirement_debt": 0,
            },
            {
                key: checker._summary(scan)[key]
                for key in (
                    "current_authored_statuses",
                    "ds1_status_rows",
                    "semantic_retirement_debt",
                )
            },
        )

    def test_ds5_override_gate_rejects_invalid_witnesses(self) -> None:
        errors, scan = self._validate(
            ATLAS_EXPORTS,
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const props: {
                  presentation?: Atlas.AuthorityPresentation;
                } = {};
                export const Probe = () =>
                  <Atlas.AuthorityBadge {...props} />;
                """
            ),
        )

        diagnostics = scan.get("overrideDiagnostics", [])
        self.assertEqual(1, len(diagnostics))
        self.assertEqual(PROBE_PATH, diagnostics[0]["path"])
        self.assertEqual(2322, diagnostics[0]["code"])
        self.assertIn("not assignable", diagnostics[0]["message"])
        self.assertTrue(
            any(error.endswith(":TS2322") for error in errors), errors
        )

    def test_structural_authority_lookalike_is_not_an_issued_brand(self) -> None:
        errors, scan = self._validate(
            ATLAS_EXPORTS,
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const forged = {
                  authority: "approved",
                  presentation: "recognized" as const,
                  source: "opaque_extension" as const,
                  tone: "ok" as const,
                };
                export const Probe = () =>
                  <Atlas.AuthorityBadge presentation={forged} />;
                """
            ),
        )

        self.assertEqual([2741], [item["code"] for item in scan["overrideDiagnostics"]])
        self.assertTrue(any(error.endswith(":TS2741") for error in errors), errors)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
