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
    raise RuntimeError(f"Unable to import enforcement checker from {ENFORCEMENT_CHECKER_PATH}")
checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(checker)

PACKAGE_PATH = "packages/atlas-ui/src/index.ts"
PROBE_PATH = "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerProbe.tsx"
TS_PROBE_PATH = "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerProbe.ts"
TYPE_SHAPES_PATH = "apps/runtime-dashboard/src/shared/lib/domain/authorityEscapeTypes.ts"
ATLAS_EXPORTS = (
    'export { AuthorityBadge } from "./primitives/AuthorityBadge";\n'
    "export type { AuthorityPresentation } from "
    '"./primitives/AuthorityBadge";\n'
    "export { createOpaqueAuthorityPresentation } from "
    '"./primitives/AuthorityBadge";\n'
    'export { EnvelopeChip } from "./primitives/EnvelopeChip";\n'
    'export { EvidenceLink } from "./primitives/EvidenceLink";\n'
    "export type { FixtureProvenance, GovernedAuthorityPurpose } from "
    '"./primitives/evidenceTypes";\n'
    'export type { BadgeTone } from "./primitives/Badge";\n'
    'export { Button } from "./primitives/Button";\n'
    'export { SegmentedControl } from "./primitives/SegmentedControl";\n'
)


def ts_source(source: str) -> str:
    """Return a line-stable TypeScript override fixture."""
    return dedent(source).strip() + "\n"


AUTHORITY_ESCAPE_TYPES = ts_source(
    """
    export interface SafeShape { payload: string }
    export interface UnsafeShape { payload: unknown }
    """
)


class AtlasEnforcementTests(unittest.TestCase):
    """Prove the retained checker states only decidable local guarantees."""

    def _validate(
        self,
        package_source: str,
        probe_source: str,
        *,
        enforce_authority_escapes: bool = False,
        probe_path: str = PROBE_PATH,
        extra_sources: dict[str, str] | None = None,
    ) -> tuple[list[str], dict[str, Any]]:
        sources = {
            PACKAGE_PATH: package_source,
            probe_path: probe_source,
        }
        sources.update(extra_sources or {})
        return checker.validate_enforcement(
            source_overrides=sources,
            enforce_authority_escapes=enforce_authority_escapes,
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
        self.assertFalse(any("packageOwnerProbe" in path for path, _prop in pairs))

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
        inventory = checker.status_checker._load_json(checker.status_checker.INVENTORY_PATH)
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
        self.assertTrue(any(error.endswith(":TS2322") for error in errors), errors)

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

    def test_branded_props_reject_raw_values_and_caller_clothing(self) -> None:
        fixtures = {
            "raw_fixture_authority": """
                import type {
                  LegacyProvingGroundPayload,
                } from "@polisyos/runtime-api-client";
                import * as Atlas from "@polisyos/atlas-ui";
                const fixtureAuthority = "fixture_only" satisfies
                  LegacyProvingGroundPayload["fixture_authority"];
                export const Probe = () =>
                  <Atlas.AuthorityBadge presentation={fixtureAuthority} />;
            """,
            "widened_string_authority": """
                import * as Atlas from "@polisyos/atlas-ui";
                const widened: string = "fixture_only";
                export const Probe = () =>
                  <Atlas.AuthorityBadge presentation={widened} />;
            """,
            "raw_fixture_provenance": """
                import type {
                  LegacyProvingGroundPayload,
                } from "@polisyos/runtime-api-client";
                import * as Atlas from "@polisyos/atlas-ui";
                const fixtureAuthority = "fixture_only" satisfies
                  LegacyProvingGroundPayload["fixture_authority"];
                export const Probe = () => <Atlas.EvidenceLink
                  evidenceRef="fixture:evidence"
                  fixtureProvenance={fixtureAuthority}
                />;
            """,
            "authority_badge_class_name": """
                import * as Atlas from "@polisyos/atlas-ui";
                const presentation =
                  Atlas.createOpaqueAuthorityPresentation("owner");
                export const Probe = () => <Atlas.AuthorityBadge
                  className="text-red-500"
                  presentation={presentation}
                />;
            """,
            "authority_badge_style": """
                import * as Atlas from "@polisyos/atlas-ui";
                const presentation =
                  Atlas.createOpaqueAuthorityPresentation("owner");
                export const Probe = () => <Atlas.AuthorityBadge
                  presentation={presentation}
                  style={{ color: "red" }}
                />;
            """,
            "envelope_chip_class_name": """
                import * as Atlas from "@polisyos/atlas-ui";
                declare const purpose: Atlas.GovernedAuthorityPurpose;
                export const Probe = () => <Atlas.EnvelopeChip
                  authorityPurpose={purpose}
                  className="text-red-500"
                />;
            """,
            "envelope_chip_style": """
                import * as Atlas from "@polisyos/atlas-ui";
                declare const purpose: Atlas.GovernedAuthorityPurpose;
                export const Probe = () => <Atlas.EnvelopeChip
                  authorityPurpose={purpose}
                  style={{ color: "red" }}
                />;
            """,
        }

        for label, fixture in fixtures.items():
            with self.subTest(label=label):
                errors, scan = self._validate(ATLAS_EXPORTS, ts_source(fixture))
                diagnostics = scan.get("overrideDiagnostics", [])
                self.assertEqual([2322], [item["code"] for item in diagnostics])
                self.assertEqual(1, len(errors), errors)
                self.assertTrue(errors[0].endswith(":TS2322"), errors)

    def test_authority_paths_reject_unregistered_type_escape_hatches(self) -> None:
        corruptions = {
            "single_assertion": """
                const presentation = Atlas.createOpaqueAuthorityPresentation(
                  "owner",
                ) as Atlas.AuthorityPresentation;
            """,
            "double_assertion": """
                const presentation =
                  {} as unknown as Atlas.AuthorityPresentation;
            """,
            "explicit_any": """
                const presentation: any =
                  Atlas.createOpaqueAuthorityPresentation("owner");
            """,
            "ts_ignore": """
                // @ts-ignore authority escape witness
                const presentation: Atlas.AuthorityPresentation = {};
            """,
            "ts_expect_error": """
                // @ts-expect-error authority escape witness
                const presentation: Atlas.AuthorityPresentation = {};
            """,
            "branded_satisfies": """
                const presentation = Atlas.createOpaqueAuthorityPresentation(
                  "owner",
                ) satisfies Atlas.AuthorityPresentation;
            """,
            "any_satisfies": """
                const presentation = Atlas.createOpaqueAuthorityPresentation(
                  "owner",
                ) satisfies any;
            """,
            "unknown_satisfies": """
                const presentation = Atlas.createOpaqueAuthorityPresentation(
                  "owner",
                ) satisfies unknown;
            """,
            "aliased_any_satisfies": """
                type EscapeAlias = any;
                const presentation = Atlas.createOpaqueAuthorityPresentation(
                  "owner",
                ) satisfies EscapeAlias;
            """,
            "interface_unknown_satisfies": """
                interface EscapeShape { payload: unknown }
                const unsafe = { payload: "owner" } satisfies EscapeShape;
                const presentation =
                  Atlas.createOpaqueAuthorityPresentation("owner");
                void unsafe;
            """,
            "type_query_unknown_satisfies": """
                declare const widening: unknown;
                const unsafe = "owner" satisfies typeof widening;
                const presentation =
                  Atlas.createOpaqueAuthorityPresentation("owner");
                void unsafe;
            """,
            "import_type_unknown_satisfies": """
                const unsafe = { payload: "owner" } satisfies
                  import("./authorityEscapeTypes").UnsafeShape;
                const presentation =
                  Atlas.createOpaqueAuthorityPresentation("owner");
                void unsafe;
            """,
            "aliased_brand_satisfies": """
                type EscapeAlias = Atlas.AuthorityPresentation;
                const presentation = Atlas.createOpaqueAuthorityPresentation(
                  "owner",
                ) satisfies EscapeAlias;
            """,
            "nested_brand_satisfies": """
                type EscapeAlias = Readonly<Atlas.AuthorityPresentation>;
                const presentation = Atlas.createOpaqueAuthorityPresentation(
                  "owner",
                ) satisfies EscapeAlias;
            """,
            "union_brand_satisfies": """
                type EscapeAlias = Atlas.AuthorityPresentation | { safe: true };
                const presentation = Atlas.createOpaqueAuthorityPresentation(
                  "owner",
                ) satisfies EscapeAlias;
            """,
            "intersection_brand_satisfies": """
                type EscapeAlias = Atlas.AuthorityPresentation & {};
                const presentation = Atlas.createOpaqueAuthorityPresentation(
                  "owner",
                ) satisfies EscapeAlias;
            """,
            "shadowed_record_satisfies": """
                import type {
                  RunOperatorProjectionStateLabel,
                } from "@polisyos/runtime-api-client";
                type Record<Key extends PropertyKey, Value> = {
                  [Property in Key]?: Value;
                };
                const incompleteMap = { approved: "ok" } satisfies Record<
                  RunOperatorProjectionStateLabel["state"],
                  Atlas.BadgeTone
                >;
                const presentation =
                  Atlas.createOpaqueAuthorityPresentation("owner");
                void incompleteMap;
            """,
        }

        for label, corruption in corruptions.items():
            with self.subTest(label=label):
                errors, scan = self._validate(
                    ATLAS_EXPORTS,
                    ts_source(
                        f"""
                        import * as Atlas from "@polisyos/atlas-ui";
                        {corruption}
                        export const Probe = () =>
                          <Atlas.AuthorityBadge presentation={{presentation}} />;
                        """
                    ),
                    enforce_authority_escapes=True,
                    extra_sources={TYPE_SHAPES_PATH: AUTHORITY_ESCAPE_TYPES},
                )
                self.assertFalse(
                    any(error.startswith("invalid_source_override:") for error in errors),
                    errors,
                )
                self.assertTrue(
                    any(error.startswith("authority_escape_") for error in errors),
                    errors,
                )
                self.assertEqual([], scan.get("overrideDiagnostics", []), errors)

    def test_authority_escape_lint_keeps_safe_resolved_types_benign(self) -> None:
        errors, scan = self._validate(
            ATLAS_EXPORTS,
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                declare const safe: { payload: string };
                const safeQuery = { payload: "owner" } satisfies typeof safe;
                const safeImport = { payload: "owner" } satisfies
                  import("./authorityEscapeTypes").SafeShape;
                const presentation =
                  Atlas.createOpaqueAuthorityPresentation("owner");
                export const Probe = () =>
                  <Atlas.AuthorityBadge presentation={presentation} />;
                void safeQuery;
                void safeImport;
                """
            ),
            enforce_authority_escapes=True,
            extra_sources={TYPE_SHAPES_PATH: AUTHORITY_ESCAPE_TYPES},
        )

        self.assertEqual([], scan.get("overrideDiagnostics", []), errors)
        self.assertFalse(
            any(error.startswith("authority_escape_") for error in errors),
            errors,
        )

    def test_authority_paths_reject_compiler_recognized_nocheck(self) -> None:
        errors, scan = self._validate(
            ATLAS_EXPORTS,
            ts_source(
                """
                // @ts-nocheck authority escape witness
                import * as Atlas from "@polisyos/atlas-ui";
                const presentation: Atlas.AuthorityPresentation = {};
                export const Probe = () =>
                  <Atlas.AuthorityBadge presentation={presentation} />;
                """
            ),
            enforce_authority_escapes=True,
        )

        self.assertEqual([], scan.get("overrideDiagnostics", []), errors)
        self.assertTrue(
            any(site.get("construct") == "ts_nocheck" for site in scan["authorityEscapeSites"]),
            scan["authorityEscapeSites"],
        )
        self.assertTrue(
            any(error.startswith("authority_escape_unregistered:") for error in errors),
            errors,
        )

    def test_authority_directive_lint_ignores_benign_prose(self) -> None:
        errors, scan = self._validate(
            ATLAS_EXPORTS,
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                // Documentation says never spell `@ts-ignore` on this path.
                const presentation =
                  Atlas.createOpaqueAuthorityPresentation("owner");
                export const Probe = () =>
                  <Atlas.AuthorityBadge presentation={presentation} />;
                """
            ),
            enforce_authority_escapes=True,
        )

        self.assertEqual([], errors)
        self.assertFalse(
            any(
                site.get("construct") in {"ts_ignore", "ts_expect_error"}
                for site in scan["authorityEscapeSites"]
            ),
            scan["authorityEscapeSites"],
        )

    def test_authority_path_derives_static_namespace_element_access(self) -> None:
        for access in ('"AuthorityBadge"', "`AuthorityBadge`"):
            with self.subTest(access=access):
                errors, scan = self._validate(
                    ATLAS_EXPORTS,
                    ts_source(
                        f"""
                        import * as Atlas from "@polisyos/atlas-ui";
                        const Sink = Atlas[{access}];
                        const forged: any = {{}};
                        export const Probe = () =>
                          <Sink presentation={{forged}} />;
                        """
                    ),
                    enforce_authority_escapes=True,
                )

                self.assertEqual([], scan.get("overrideDiagnostics", []), errors)
                self.assertTrue(
                    any(row["path"] == PROBE_PATH for row in scan["authorityPathFiles"]),
                    scan["authorityPathFiles"],
                )
                self.assertTrue(
                    any(
                        site.get("construct") == "explicit_any"
                        for site in scan["authorityEscapeSites"]
                    ),
                    scan["authorityEscapeSites"],
                )
                self.assertTrue(
                    any(error.startswith("authority_escape_unregistered:") for error in errors),
                    errors,
                )

    def test_authority_paths_reject_angle_bracket_assertion(self) -> None:
        errors, scan = self._validate(
            ATLAS_EXPORTS,
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const issued = Atlas.createOpaqueAuthorityPresentation("owner");
                const presentation = <Atlas.AuthorityPresentation>issued;
                void presentation;
                """
            ),
            enforce_authority_escapes=True,
            probe_path=TS_PROBE_PATH,
        )

        self.assertEqual([], scan.get("overrideDiagnostics", []), errors)
        self.assertTrue(
            any(site.get("construct") == "type_assertion" for site in scan["authorityEscapeSites"]),
            scan["authorityEscapeSites"],
        )
        self.assertTrue(
            any(error.startswith("authority_escape_unregistered:") for error in errors),
            errors,
        )

    def test_authority_escape_lint_keeps_generated_conformance_benign(self) -> None:
        errors, _scan = self._validate(
            ATLAS_EXPORTS,
            ts_source(
                """
                import type {
                  RunOperatorProjectionStateLabel,
                } from "@polisyos/runtime-api-client";
                import * as Atlas from "@polisyos/atlas-ui";
                const label = {
                  authority: "runtime_authority",
                  label: "owner label",
                  state: "rejected",
                } satisfies RunOperatorProjectionStateLabel;
                const presentation =
                  Atlas.createOpaqueAuthorityPresentation(label.label);
                export const Probe = () =>
                  <Atlas.AuthorityBadge presentation={presentation} />;
                """
            ),
            enforce_authority_escapes=True,
        )

        self.assertFalse(
            any(error.startswith("authority_escape_") for error in errors),
            errors,
        )

    def test_authority_path_derivation_ignores_unrelated_namespace_use(self) -> None:
        errors, scan = self._validate(
            ATLAS_EXPORTS,
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const options = ["primary", "secondary"] as const;
                const Control = Atlas["Button"];
                export const Probe = () => <Control>{options[0]}</Control>;
                """
            ),
            enforce_authority_escapes=True,
        )

        self.assertFalse(any(row["path"] == PROBE_PATH for row in scan["authorityPathFiles"]))
        self.assertFalse(
            any(error.startswith("authority_escape_") for error in errors),
            errors,
        )

    def test_authority_escape_exemptions_are_exact_owned_and_current(self) -> None:
        errors, scan = checker.validate_enforcement(enforce_authority_escapes=False)
        self.assertEqual([], errors)
        self.assertEqual([], checker._authority_escape_errors(scan))

        current = checker.AUTHORITY_ESCAPE_EXEMPTIONS[0]
        mutations = {
            "moved": current._replace(line=current.line + 1),
            "unknown_path": current._replace(path="packages/atlas-ui/src/unknown.ts"),
            "reasonless": current._replace(reason=""),
            "ownerless": current._replace(owner=""),
            "unknown_construct": current._replace(construct="escape"),
        }
        for label, mutation in mutations.items():
            with self.subTest(label=label):
                mutation_errors = checker._authority_escape_errors(
                    scan,
                    exemptions=(mutation, *checker.AUTHORITY_ESCAPE_EXEMPTIONS[1:]),
                )
                self.assertTrue(mutation_errors, label)
                self.assertTrue(
                    any(current.exemption_id in error for error in mutation_errors),
                    mutation_errors,
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
