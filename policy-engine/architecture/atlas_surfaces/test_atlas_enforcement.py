"""Behavioral tests for Atlas cross-package authority enforcement."""

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
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import bootstrap guard
    raise RuntimeError(
        f"Unable to import enforcement checker from {ENFORCEMENT_CHECKER_PATH}"
    )
checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(checker)

PACKAGE_PATH = "packages/atlas-ui/src/index.ts"
PROBE_PATH = (
    "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerProbe.tsx"
)
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
    """Prove package-local authority cannot cross a real semantic sink."""

    def _validate(
        self,
        package_source: str,
        probe_source: str | None = None,
        *,
        extra_sources: dict[str, str] | None = None,
    ) -> tuple[list[str], dict[str, Any]]:
        sources = {PACKAGE_PATH: package_source}
        if probe_source is not None:
            sources[PROBE_PATH] = probe_source
        if extra_sources:
            sources.update(extra_sources)
        return checker.validate_enforcement(source_overrides=sources)

    @staticmethod
    def _owner_names(scan: dict[str, Any]) -> set[str]:
        return {
            str(finding.get("declarationName") or finding.get("fieldName"))
            for finding in scan.get("unauthorizedStatusOwners", [])
        }

    @staticmethod
    def _sink_owner_names(scan: dict[str, Any], field: str) -> set[str]:
        return {
            str(finding.get("ownerDeclarationName") or finding.get("ownerFieldName"))
            for finding in scan.get("unauthorizedStatusSinks", [])
            if finding.get("sinkField") == field
        }

    def test_sink_reachability_is_name_independent_and_unused_unions_are_benign(
        self,
    ) -> None:
        errors, scan = self._validate(
            ATLAS_EXPORTS
            + 'export type UnusedDecisionStatus = "ready" | "blocked";\n'
            + 'export type DecisionPosture = "ready" | "blocked";\n'
            + 'export type OutcomeMode = "ready" | "blocked";\n'
            + 'export type ReviewPhase = "ready" | "blocked";\n'
            + "export const keepPosture = (value: DecisionPosture) => value;\n"
            + "export const keepMode = (value: OutcomeMode) => value;\n"
            + "export const keepPhase = (value: ReviewPhase) => value;\n",
            'import * as Atlas from "@polisyos/atlas-ui";\n'
            "export function Probe() {\n"
            + '  const posture = Atlas.keepPosture("ready");\n'
            + '  const mode = Atlas.keepMode("ready");\n'
            + '  const phase = Atlas.keepPhase("ready");\n'
            + "  return <>\n"
            + "    <Atlas.AuthorityBadge presentation={posture as unknown as "
            + "Atlas.AuthorityPresentation} />\n"
            + "    <Atlas.AuthorityBadge presentation={mode as unknown as "
            + "Atlas.AuthorityPresentation} />\n"
            + "    <Atlas.AuthorityBadge presentation={phase as unknown as "
            + "Atlas.AuthorityPresentation} />\n"
            + "  </>;\n"
            + "}\n",
        )

        owner_names = self._owner_names(scan)
        self.assertEqual(
            {"DecisionPosture", "OutcomeMode", "ReviewPhase"},
            owner_names,
        )
        self.assertEqual(
            {"DecisionPosture", "OutcomeMode", "ReviewPhase"},
            self._sink_owner_names(scan, "presentation"),
        )
        self.assertNotIn("UnusedDecisionStatus", owner_names)
        self.assertIn(
            f"unauthorized_status_owner:{PACKAGE_PATH}:ReviewPhase",
            errors,
        )
        self.assertIn(
            f"unauthorized_status_sink:{PROBE_PATH}:presentation",
            errors,
        )

    def test_generated_owner_requires_exact_governed_artifact_provenance(
        self,
    ) -> None:
        fake_path = "packages/runtime-api-client/fake.ts"
        errors, scan = self._validate(
            'import type { VerificationMetadata } from '
            '"@polisyos/runtime-api-client";\n'
            + 'import type { FakeGenerated } from '
            + '"../../runtime-api-client/fake";\n'
            + ATLAS_EXPORTS
            + "export type GovernedDirect = "
            + 'VerificationMetadata["verification_status"];\n'
            + "type GovernedBase = "
            + 'VerificationMetadata["dispute_status"];\n'
            + "export type GovernedNested = GovernedBase;\n"
            + "type LocalShape = { outcome: \"ready\" | \"blocked\" };\n"
            + 'export type LocalLookalike = LocalShape["outcome"];\n'
            + "export type PrefixLookalike = "
            + 'FakeGenerated["outcome"];\n'
            + "export const keepGovernedDirect = "
            + "(value: GovernedDirect) => value;\n"
            + "export const keepGovernedNested = "
            + "(value: GovernedNested) => value;\n"
            + "export const keepLocal = (value: LocalLookalike) => value;\n"
            + "export const keepPrefix = (value: PrefixLookalike) => value;\n",
            'import * as Atlas from "@polisyos/atlas-ui";\n'
            + "const cast = (value: unknown) => "
            + "value as Atlas.AuthorityPresentation;\n"
            + "export function Probe() {\n"
            + '  const direct = Atlas.keepGovernedDirect("verified");\n'
            + '  const nested = Atlas.keepGovernedNested("none");\n'
            + '  const local = Atlas.keepLocal("ready");\n'
            + '  const prefix = Atlas.keepPrefix("ready");\n'
            + "  return <>\n"
            + "    <Atlas.AuthorityBadge presentation={cast(direct)} />\n"
            + "    <Atlas.AuthorityBadge presentation={cast(nested)} />\n"
            + "    <Atlas.AuthorityBadge presentation={cast(local)} />\n"
            + "    <Atlas.AuthorityBadge presentation={cast(prefix)} />\n"
            + "  </>;\n"
            + "}\n",
            extra_sources={
                fake_path: (
                    "export interface FakeGenerated {\n"
                    '  outcome: "ready" | "blocked";\n'
                    "}\n"
                )
            },
        )

        owner_names = self._owner_names(scan)
        self.assertEqual({"LocalLookalike", "PrefixLookalike"}, owner_names)
        self.assertNotIn("GovernedDirect", owner_names)
        self.assertNotIn("GovernedNested", owner_names)
        self.assertIn(
            f"unauthorized_status_owner:{PACKAGE_PATH}:PrefixLookalike",
            errors,
        )

    def test_package_namespace_alias_later_assignment_jsx_spread_revival_fails(
        self,
    ) -> None:
        errors, scan = self._validate(
            ATLAS_EXPORTS
            + 'export type ReviewPhase = "admissible" | "blocked";\n'
            + "export function preserve(value: ReviewPhase) { return value; }\n",
            'import * as Atlas from "@polisyos/atlas-ui";\n'
            + "function wrapOwner(value: Atlas.ReviewPhase) {\n"
            + "  return Atlas.preserve(value);\n"
            + "}\n"
            + "export function Probe() {\n"
            + '  const carrier = { selected: wrapOwner("admissible"), '\
            + 'presentation: "neutral" };\n'
            + "  const values = [carrier.selected];\n"
            + "  const [picked] = values;\n"
            + "  let later;\n"
            + "  later = picked;\n"
            + "  const holder: { chosen?: unknown } = {};\n"
            + "  holder.chosen = later;\n"
            + "  const presentation = "
            + "holder.chosen as Atlas.AuthorityPresentation;\n"
            + "  let authorityProps: { presentation: "
            + "Atlas.AuthorityPresentation };\n"
            + "  authorityProps = { presentation };\n"
            + "  return <Atlas.AuthorityBadge {...authorityProps} />;\n"
            + "}\n",
        )

        self.assertEqual({"ReviewPhase"}, self._owner_names(scan))
        self.assertEqual(
            {"ReviewPhase"},
            self._sink_owner_names(scan, "presentation"),
        )
        presentation_sinks = [
            finding
            for finding in scan["unauthorizedStatusSinks"]
            if finding["sinkField"] == "presentation"
        ]
        self.assertTrue(presentation_sinks)
        self.assertTrue(
            all(
                finding["sinkDeclarationPath"]
                == "packages/atlas-ui/src/primitives/AuthorityBadge.tsx"
                for finding in presentation_sinks
            )
        )
        self.assertIn(
            f"unauthorized_status_owner:{PACKAGE_PATH}:ReviewPhase",
            errors,
        )
        self.assertIn(
            f"unauthorized_status_sink:{PROBE_PATH}:presentation",
            errors,
        )

    def test_owner_graph_is_field_call_and_carrier_sensitive(self) -> None:
        package = (
            ATLAS_EXPORTS
            + 'export type ReviewPhase = "admissible" | "blocked";\n'
            + "export function preserve(value: ReviewPhase) { return value; }\n"
        )
        benign_cases = {
            "discarded argument": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "const independent = {} as Atlas.AuthorityPresentation;\n"
                + "function discard(_value: unknown) { return independent; }\n"
                + "export function Probe() {\n"
                + '  const owner = Atlas.preserve("admissible");\n'
                + "  return <Atlas.AuthorityBadge "
                + "presentation={discard(owner)} />;\n"
                + "}\n"
            ),
            "independent sibling": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "const independent = {} as Atlas.AuthorityPresentation;\n"
                + "export function Probe() {\n"
                + '  const owner = Atlas.preserve("admissible");\n'
                + "  const carrier = { owner, presentation: independent };\n"
                + "  return <Atlas.AuthorityBadge "
                + "presentation={carrier.presentation} />;\n"
                + "}\n"
            ),
            "removed return edge": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "const independent = {} as Atlas.AuthorityPresentation;\n"
                + "function wrap(_value: Atlas.ReviewPhase) {\n"
                + "  return independent;\n"
                + "}\n"
                + "export function Probe() {\n"
                + '  const owner = Atlas.preserve("admissible");\n'
                + "  return <Atlas.AuthorityBadge "
                + "presentation={wrap(owner)} />;\n"
                + "}\n"
            ),
            "removed selected-field edge": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "const independent = {} as Atlas.AuthorityPresentation;\n"
                + "export function Probe() {\n"
                + '  const owner = Atlas.preserve("admissible");\n'
                + "  const carrier = { owner, selected: independent };\n"
                + "  const props = { presentation: carrier.selected };\n"
                + "  return <Atlas.AuthorityBadge {...props} />;\n"
                + "}\n"
            ),
            "explicit property overwrites owner spread": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "const independent = {} as Atlas.AuthorityPresentation;\n"
                + "export function Probe() {\n"
                + '  const owner = Atlas.preserve("admissible") '
                + "as unknown as Atlas.AuthorityPresentation;\n"
                + "  const tainted = { presentation: owner };\n"
                + "  const props = { ...tainted, presentation: independent };\n"
                + "  return <Atlas.AuthorityBadge {...props} />;\n"
                + "}\n"
            ),
            "constant index selects independent element": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "const independent = {} as Atlas.AuthorityPresentation;\n"
                + "export function Probe() {\n"
                + '  const owner = Atlas.preserve("admissible");\n'
                + "  const values = [owner, independent];\n"
                + "  return <Atlas.AuthorityBadge "
                + "presentation={values[1] as "
                + "Atlas.AuthorityPresentation} />;\n"
                + "}\n"
            ),
            "separate call site stays independent": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "const independent = {} as Atlas.AuthorityPresentation;\n"
                + "function identity<T>(value: T) { return value; }\n"
                + "export function Probe() {\n"
                + '  identity(Atlas.preserve("admissible"));\n'
                + "  const presentation = identity(independent);\n"
                + "  return <Atlas.AuthorityBadge {"
                + "...{ presentation }} />;\n"
                + "}\n"
            ),
            "removed array edge": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "const independent = {} as Atlas.AuthorityPresentation;\n"
                + "export function Probe() {\n"
                + '  const owner = Atlas.preserve("admissible");\n'
                + "  const carrier = { selected: owner };\n"
                + "  const values = [independent];\n"
                + "  const [presentation] = values;\n"
                + "  return <Atlas.AuthorityBadge {"
                + "...{ presentation }} />;\n"
                + "}\n"
            ),
            "removed destructuring edge": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "const independent = {} as Atlas.AuthorityPresentation;\n"
                + "export function Probe() {\n"
                + '  const owner = Atlas.preserve("admissible");\n'
                + "  const values = [independent, owner] as const;\n"
                + "  const [presentation] = values;\n"
                + "  return <Atlas.AuthorityBadge {"
                + "...{ presentation }} />;\n"
                + "}\n"
            ),
            "removed later-variable edge": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "const independent = {} as Atlas.AuthorityPresentation;\n"
                + "export function Probe() {\n"
                + '  const owner = Atlas.preserve("admissible");\n'
                + "  let presentation;\n"
                + "  presentation = independent;\n"
                + "  return <Atlas.AuthorityBadge {"
                + "...{ presentation }} />;\n"
                + "}\n"
            ),
            "removed later-property edge": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "const independent = {} as Atlas.AuthorityPresentation;\n"
                + "export function Probe() {\n"
                + '  const owner = Atlas.preserve("admissible");\n'
                + "  const props = {} as { presentation: "
                + "Atlas.AuthorityPresentation };\n"
                + "  props.presentation = independent;\n"
                + "  return <Atlas.AuthorityBadge {...props} />;\n"
                + "}\n"
            ),
        }
        for label, source in benign_cases.items():
            with self.subTest(label=label):
                errors, scan = self._validate(package, source)
                self.assertEqual([], errors)
                self.assertEqual([], scan["unauthorizedStatusOwners"])
                self.assertEqual([], scan["unauthorizedStatusSinks"])

        failing_cases = {
            "later property assignment": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "export function Probe() {\n"
                + '  const presentation = Atlas.preserve("admissible") '
                + "as unknown as Atlas.AuthorityPresentation;\n"
                + "  const props = {} as { presentation: "
                + "Atlas.AuthorityPresentation };\n"
                + "  props.presentation = presentation;\n"
                + "  return <Atlas.AuthorityBadge {...props} />;\n"
                + "}\n"
            ),
            "shorthand wrapper-returned object": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "export function Probe() {\n"
                + "  function propsFor(value: Atlas.ReviewPhase) {\n"
                + "  const presentation = "
                + "value as unknown as Atlas.AuthorityPresentation;\n"
                + "  return { presentation };\n"
                + "}\n"
                + '  const owner = Atlas.preserve("admissible");\n'
                + "  return <Atlas.AuthorityBadge {...propsFor(owner)} />;\n"
                + "}\n"
            ),
        }
        for label, source in failing_cases.items():
            with self.subTest(label=label):
                errors, scan = self._validate(package, source)
                self.assertIn(
                    f"unauthorized_status_sink:{PROBE_PATH}:presentation",
                    errors,
                )
                self.assertEqual(
                    {"ReviewPhase"},
                    self._sink_owner_names(scan, "presentation"),
                )

    def test_declaration_bound_lifecycle_sinks_preserve_owner_provenance(
        self,
    ) -> None:
        package = (
            ATLAS_EXPORTS
            + 'export type ReviewPhase = "admissible" | "blocked";\n'
            + "export function preserve(value: ReviewPhase) { return value; }\n"
        )
        errors, scan = self._validate(
            package,
            'import * as Atlas from "@polisyos/atlas-ui";\n'
            + "export function Probe() {\n"
            + '  const owner = Atlas.preserve("admissible");\n'
            + '  const blocked = owner === "blocked";\n'
            + "  return <Atlas.Button disabled={blocked} "
            + 'aria-disabled={blocked}>Review</Atlas.Button>;\n'
            + "}\n",
        )

        lifecycle = {
            finding["sinkField"]: finding
            for finding in scan.get("unauthorizedStatusSinks", [])
            if finding["sinkField"] in {"disabled", "aria-disabled"}
        }
        self.assertEqual({"disabled", "aria-disabled"}, set(lifecycle))
        for field, finding in lifecycle.items():
            self.assertEqual("ReviewPhase", finding["ownerDeclarationName"])
            self.assertEqual(
                "packages/atlas-ui/src/primitives/Button.tsx",
                finding["sinkDeclarationPath"],
            )
            self.assertIn(
                f"unauthorized_status_sink:{PROBE_PATH}:{field}", errors
            )

        spread_errors, spread_scan = self._validate(
            package,
            'import * as Atlas from "@polisyos/atlas-ui";\n'
            + "export function Probe() {\n"
            + '  const owner = Atlas.preserve("admissible");\n'
            + '  const blocked = owner === "blocked";\n'
            + "  const lifecycle = { disabled: blocked, "
            + '"aria-disabled": blocked };\n'
            + "  return <Atlas.Button {...lifecycle}>Review</Atlas.Button>;\n"
            + "}\n",
        )
        self.assertEqual(
            {"disabled", "aria-disabled"},
            {
                finding["sinkField"]
                for finding in spread_scan["unauthorizedStatusSinks"]
            },
        )
        self.assertIn(
            f"unauthorized_status_sink:{PROBE_PATH}:disabled", spread_errors
        )

        benign_errors, benign_scan = self._validate(
            package,
            'import * as Atlas from "@polisyos/atlas-ui";\n'
            + "export function Probe() {\n"
            + "  const width = 1024;\n"
            + "  const compact = width < 768;\n"
            + "  const tabIndex = compact ? -1 : 0;\n"
            + "  return <Atlas.Button fullWidth={compact} "
            + "tabIndex={tabIndex}>Review</Atlas.Button>;\n"
            + "}\n",
        )
        self.assertEqual([], benign_errors)
        self.assertEqual([], benign_scan["unauthorizedStatusOwners"])
        self.assertEqual([], benign_scan["unauthorizedStatusSinks"])

    def test_generated_exemption_requires_every_union_branch_to_resolve(
        self,
    ) -> None:
        fake_path = "packages/runtime-api-client/fake.ts"
        errors, scan = self._validate(
            ts_source(
                """
                import type { VerificationMetadata } from
                  "@polisyos/runtime-api-client";
                import type { FakeGenerated } from
                  "../../runtime-api-client/fake";
                export { AuthorityBadge } from "./primitives/AuthorityBadge";
                export type { AuthorityPresentation } from
                  "./primitives/AuthorityBadge";

                type GeneratedVerification =
                  VerificationMetadata["verification_status"];
                type GeneratedDispute =
                  VerificationMetadata["dispute_status"];
                export type GeneratedOnly =
                  GeneratedVerification | GeneratedDispute;
                export type MixedDirect =
                  VerificationMetadata["verification_status"] | "atlas_local";
                type LocalBranch = "local_a" | "local_b";
                type MixedBase = GeneratedDispute | LocalBranch;
                export type MixedNested = MixedBase;
                export type LocalIndexed =
                  { outcome: "local_a" | "local_b" }["outcome"];
                export type PrefixIndexed = FakeGenerated["outcome"];

                export const keepGenerated = (value: GeneratedOnly) => value;
                export const keepMixedDirect = (value: MixedDirect) => value;
                export const keepMixedNested = (value: MixedNested) => value;
                export const keepLocal = (value: LocalIndexed) => value;
                export const keepPrefix = (value: PrefixIndexed) => value;
                """
            ),
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const cast = (value: unknown) =>
                  value as Atlas.AuthorityPresentation;
                export function Probe() {
                  const generated = Atlas.keepGenerated("verified");
                  const direct = Atlas.keepMixedDirect("atlas_local");
                  const nested = Atlas.keepMixedNested("local_a");
                  const local = Atlas.keepLocal("local_a");
                  const prefix = Atlas.keepPrefix("local_a");
                  return <>
                    <Atlas.AuthorityBadge presentation={cast(generated)} />
                    <Atlas.AuthorityBadge presentation={cast(direct)} />
                    <Atlas.AuthorityBadge presentation={cast(nested)} />
                    <Atlas.AuthorityBadge presentation={cast(local)} />
                    <Atlas.AuthorityBadge presentation={cast(prefix)} />
                  </>;
                }
                """
            ),
            extra_sources={
                fake_path: ts_source(
                    """
                    export interface FakeGenerated {
                      outcome: "local_a" | "local_b";
                    }
                    """
                )
            },
        )

        self.assertEqual(
            {"MixedDirect", "MixedNested", "LocalIndexed", "PrefixIndexed"},
            self._owner_names(scan),
        )
        self.assertEqual(
            {"MixedDirect", "MixedNested", "LocalIndexed", "PrefixIndexed"},
            self._sink_owner_names(scan, "presentation"),
        )
        self.assertNotIn("GeneratedOnly", self._owner_names(scan))
        self.assertIn(
            f"unauthorized_status_owner:{PACKAGE_PATH}:MixedDirect", errors
        )

    def test_ds5_override_gate_rejects_invalid_witnesses(self) -> None:
        package = ts_source(
            """
            export { AuthorityBadge } from "./primitives/AuthorityBadge";
            export type { AuthorityPresentation } from
              "./primitives/AuthorityBadge";
            export type CivicVector = "open" | "closed";
            export const preserve = (value: CivicVector) => value;
            """
        )
        invalid_probe = ts_source(
            """
            import * as Atlas from "@polisyos/atlas-ui";
            export function Probe() {
              const presentation = Atlas.preserve("closed") as unknown as
                Atlas.AuthorityPresentation;
              const props: { presentation?: Atlas.AuthorityPresentation } = {
                presentation,
              };
              return <Atlas.AuthorityBadge {...props} />;
            }
            """
        )

        errors, scan = self._validate(package, invalid_probe)
        diagnostics = scan.get("overrideDiagnostics", [])
        self.assertEqual(1, len(diagnostics))
        self.assertEqual(PROBE_PATH, diagnostics[0]["path"])
        self.assertEqual(8, diagnostics[0]["line"])
        self.assertGreater(diagnostics[0]["column"], 0)
        self.assertEqual(2322, diagnostics[0]["code"])
        self.assertIn("not assignable", diagnostics[0]["message"])
        self.assertIn(
            f"invalid_source_override:{PROBE_PATH}:8:TS2322", errors
        )

        inventory = checker.status_checker._load_json(
            checker.status_checker.INVENTORY_PATH
        )
        legacy_scan = checker.status_checker._scan(
            {PACKAGE_PATH: package, PROBE_PATH: invalid_probe},
            inventory=inventory,
        )
        self.assertNotIn("overrideDiagnostics", legacy_scan)

    def test_program_points_preserve_alias_identity_and_effective_jsx_overwrites(
        self,
    ) -> None:
        errors, scan = self._validate(
            ts_source(
                """
                export { AuthorityBadge } from "./primitives/AuthorityBadge";
                export type { AuthorityPresentation } from
                  "./primitives/AuthorityBadge";
                export type AliasVector = "open" | "closed";
                export type NestedVector = "open" | "closed";
                export type ComputedVector = "open" | "closed";
                export type BeforeVector = "open" | "closed";
                export type AfterVector = "open" | "closed";
                export type SpreadThenDirectVector = "open" | "closed";
                export type DirectThenSpreadVector = "open" | "closed";
                export type CleanSpreadThenDirectVector = "open" | "closed";
                export type CleanDirectThenSpreadVector = "open" | "closed";
                export type SiblingVector = "open" | "closed";
                export const alias = (value: AliasVector) => value;
                export const nested = (value: NestedVector) => value;
                export const computed = (value: ComputedVector) => value;
                export const before = (value: BeforeVector) => value;
                export const after = (value: AfterVector) => value;
                export const spreadThenDirect =
                  (value: SpreadThenDirectVector) => value;
                export const directThenSpread =
                  (value: DirectThenSpreadVector) => value;
                export const cleanSpreadThenDirect =
                  (value: CleanSpreadThenDirectVector) => value;
                export const cleanDirectThenSpread =
                  (value: CleanDirectThenSpreadVector) => value;
                export const sibling = (value: SiblingVector) => value;
                """
            ),
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const independent = {} as Atlas.AuthorityPresentation;
                export function Probe() {
                  const aliasProps = { presentation: independent };
                  const alias = aliasProps;
                  alias.presentation = Atlas.alias("closed") as unknown as
                    Atlas.AuthorityPresentation;

                  const nestedProps = { inner: { presentation: independent } };
                  const nestedAlias = nestedProps.inner;
                  nestedAlias["presentation"] =
                    Atlas.nested("closed") as unknown as
                      Atlas.AuthorityPresentation;

                  const computedProps = {
                    presentation: Atlas.computed("closed") as unknown as
                      Atlas.AuthorityPresentation,
                  };
                  const field: "presentation" = "presentation";

                  let before = Atlas.before("closed") as unknown as
                    Atlas.AuthorityPresentation;
                  const beforeRendered =
                    <Atlas.AuthorityBadge presentation={before} />;
                  before = independent;

                  let after = independent;
                  const afterRendered =
                    <Atlas.AuthorityBadge presentation={after} />;
                  after = Atlas.after("closed") as unknown as
                    Atlas.AuthorityPresentation;

                  const spreadThenDirect = Atlas.spreadThenDirect("closed") as
                    unknown as Atlas.AuthorityPresentation;
                  const directThenSpread = Atlas.directThenSpread("closed") as
                    unknown as Atlas.AuthorityPresentation;
                  const cleanSpreadThenDirect =
                    Atlas.cleanSpreadThenDirect("closed") as unknown as
                      Atlas.AuthorityPresentation;
                  const cleanDirectThenSpread =
                    Atlas.cleanDirectThenSpread("closed") as unknown as
                      Atlas.AuthorityPresentation;
                  const independentSpread = {
                    presentation: independent,
                  } as Record<string, unknown>;
                  const cleanDirectSpread = {
                    presentation: cleanDirectThenSpread,
                  } as Record<string, unknown>;

                  const sibling = {
                    owner: Atlas.sibling("closed") as unknown as
                      Atlas.AuthorityPresentation,
                    presentation: independent,
                  };
                  const dynamicKey: "owner" | "presentation" =
                    Math.random() > 0.5 ? "owner" : "presentation";
                  sibling[dynamicKey] = independent;

                  return <>
                    <Atlas.AuthorityBadge {...aliasProps} />
                    <Atlas.AuthorityBadge {...nestedProps.inner} />
                    <Atlas.AuthorityBadge
                      presentation={computedProps[field]}
                    />
                    {beforeRendered}
                    {afterRendered}
                    <Atlas.AuthorityBadge
                      {...{ presentation: spreadThenDirect }}
                      presentation={independent}
                    />
                    <Atlas.AuthorityBadge
                      presentation={directThenSpread}
                      {...independentSpread}
                    />
                    <Atlas.AuthorityBadge
                      {...{ presentation: independent }}
                      presentation={cleanSpreadThenDirect}
                    />
                    <Atlas.AuthorityBadge
                      presentation={independent}
                      {...cleanDirectSpread}
                    />
                    <Atlas.AuthorityBadge presentation={sibling.presentation} />
                  </>;
                }
                """
            ),
        )

        expected = {
            "AliasVector",
            "NestedVector",
            "ComputedVector",
            "BeforeVector",
            "CleanSpreadThenDirectVector",
            "CleanDirectThenSpreadVector",
        }
        self.assertEqual(expected, self._owner_names(scan))
        self.assertEqual(expected, self._sink_owner_names(scan, "presentation"))
        self.assertNotIn("AfterVector", self._owner_names(scan))
        self.assertNotIn("SpreadThenDirectVector", self._owner_names(scan))
        self.assertNotIn("DirectThenSpreadVector", self._owner_names(scan))
        self.assertNotIn("SiblingVector", self._owner_names(scan))
        self.assertIn(
            f"unauthorized_status_sink:{PROBE_PATH}:presentation", errors
        )

    def test_cfg_handles_computed_keys_closures_control_flow_and_higher_order_calls(
        self,
    ) -> None:
        errors, scan = self._validate(
            ts_source(
                """
                export { AuthorityBadge } from "./primitives/AuthorityBadge";
                export type { AuthorityPresentation } from
                  "./primitives/AuthorityBadge";
                export type ClosureVector = "open" | "closed";
                export type LoopVector = "open" | "closed";
                export type SwitchVector = "open" | "closed";
                export type TryVector = "open" | "closed";
                export type ApplyVector = "open" | "closed";
                export type SeparateVector = "open" | "closed";
                export type DiscardVector = "open" | "closed";
                export const closure = (value: ClosureVector) => value;
                export const loop = (value: LoopVector) => value;
                export const switched = (value: SwitchVector) => value;
                export const tried = (value: TryVector) => value;
                export const applyOwner = (value: ApplyVector) => value;
                export const separate = (value: SeparateVector) => value;
                export const discarded = (value: DiscardVector) => value;
                """
            ),
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const independent = {} as Atlas.AuthorityPresentation;
                function apply<T, U>(fn: (value: T) => U, value: T): U {
                  return fn(value);
                }
                function discard(_value: unknown) {
                  return independent;
                }
                export function Probe() {
                  let closurePresentation = independent;
                  function setClosure() {
                    closurePresentation = Atlas.closure("closed") as unknown as
                      Atlas.AuthorityPresentation;
                  }
                  setClosure();

                  let loopPresentation = independent;
                  for (const value of [Atlas.loop("closed")]) {
                    loopPresentation = value as unknown as
                      Atlas.AuthorityPresentation;
                  }

                  let switchPresentation = independent;
                  const switchOwner = Atlas.switched("closed");
                  switch (switchOwner) {
                    case "open":
                    case "closed":
                      switchPresentation = switchOwner as unknown as
                        Atlas.AuthorityPresentation;
                      break;
                  }

                  let tryPresentation = independent;
                  try {
                    tryPresentation = independent;
                  } finally {
                    tryPresentation = Atlas.tried("closed") as unknown as
                      Atlas.AuthorityPresentation;
                  }

                  const applyOwner = Atlas.applyOwner("closed");
                  const applyPresentation = apply(
                    (value) => value as unknown as Atlas.AuthorityPresentation,
                    applyOwner,
                  );

                  apply((value) => value, Atlas.separate("closed"));
                  const separatePresentation = apply(
                    (value) => value,
                    independent,
                  );
                  const discardedPresentation = discard(
                    Atlas.discarded("closed"),
                  );

                  return <>
                    <Atlas.AuthorityBadge presentation={closurePresentation} />
                    <Atlas.AuthorityBadge presentation={loopPresentation} />
                    <Atlas.AuthorityBadge presentation={switchPresentation} />
                    <Atlas.AuthorityBadge presentation={tryPresentation} />
                    <Atlas.AuthorityBadge presentation={applyPresentation} />
                    <Atlas.AuthorityBadge presentation={separatePresentation} />
                    <Atlas.AuthorityBadge presentation={discardedPresentation} />
                  </>;
                }
                """
            ),
        )

        expected = {
            "ClosureVector",
            "LoopVector",
            "SwitchVector",
            "TryVector",
            "ApplyVector",
        }
        self.assertEqual(expected, self._owner_names(scan))
        self.assertEqual(expected, self._sink_owner_names(scan, "presentation"))
        self.assertNotIn("SeparateVector", self._owner_names(scan))
        self.assertNotIn("DiscardVector", self._owner_names(scan))
        self.assertIn(
            f"unauthorized_status_sink:{PROBE_PATH}:presentation", errors
        )

    def test_recursive_scc_reaches_fixed_point_without_depth_cutoff(self) -> None:
        errors, scan = self._validate(
            ts_source(
                """
                export { AuthorityBadge } from "./primitives/AuthorityBadge";
                export type { AuthorityPresentation } from
                  "./primitives/AuthorityBadge";
                export type DirectRecursiveVector = "open" | "closed";
                export type MutualRecursiveVector = "open" | "closed";
                export type BenignRecursiveVector = "open" | "closed";
                export const directRecursive =
                  (value: DirectRecursiveVector) => value;
                export const mutualRecursive =
                  (value: MutualRecursiveVector) => value;
                export const benignRecursive =
                  (value: BenignRecursiveVector) => value;
                """
            ),
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const independent = {} as Atlas.AuthorityPresentation;
                type Box = { next?: Box; value?: unknown };
                function direct(value: unknown, depth: number): Box {
                  if (depth <= 0) return { value };
                  return { next: direct(value, depth - 1) };
                }
                function even(value: unknown, depth: number): Box {
                  if (depth <= 0) return { value };
                  return { next: odd(value, depth - 1) };
                }
                function odd(value: unknown, depth: number): Box {
                  if (depth <= 0) return { value };
                  return { next: even(value, depth - 1) };
                }
                function benign(_value: unknown, depth: number): Box {
                  if (depth <= 0) return { value: independent };
                  return { next: benign(_value, depth - 1) };
                }
                export function Probe() {
                  const directBox = direct(
                    Atlas.directRecursive("closed"),
                    16,
                  );
                  const mutualBox = even(
                    Atlas.mutualRecursive("closed"),
                    16,
                  );
                  const benignBox = benign(
                    Atlas.benignRecursive("closed"),
                    16,
                  );
                  const directPresentation = directBox.next!.next!.next!.next!
                    .next!.next!.next!.next!.next!.next!.next!.next!.next!
                    .next!.next!.next!.value as
                      Atlas.AuthorityPresentation;
                  const mutualPresentation = mutualBox.next!.next!.next!.next!
                    .next!.next!.next!.next!.next!.next!.next!.next!.next!
                    .next!.next!.next!.value as
                      Atlas.AuthorityPresentation;
                  const benignPresentation = benignBox.next!.next!.next!.next!
                    .next!.next!.next!.next!.next!.next!.next!.next!.next!
                    .next!.next!.next!.value as
                      Atlas.AuthorityPresentation;
                  return <>
                    <Atlas.AuthorityBadge presentation={directPresentation} />
                    <Atlas.AuthorityBadge presentation={mutualPresentation} />
                    <Atlas.AuthorityBadge presentation={benignPresentation} />
                  </>;
                }
                """
            ),
        )

        expected = {"DirectRecursiveVector", "MutualRecursiveVector"}
        self.assertEqual(expected, self._owner_names(scan))
        self.assertEqual(expected, self._sink_owner_names(scan, "presentation"))
        self.assertNotIn("BenignRecursiveVector", self._owner_names(scan))
        self.assertIn(
            f"unauthorized_status_sink:{PROBE_PATH}:presentation", errors
        )

    def test_call_boundary_projects_captures_and_reachable_heap_effects(
        self,
    ) -> None:
        errors, scan = self._validate(
            ts_source(
                """
                export { AuthorityBadge } from "./primitives/AuthorityBadge";
                export type { AuthorityPresentation } from
                  "./primitives/AuthorityBadge";
                export type CapturedWriteVector = "open" | "closed";
                export type ArgumentWriteVector = "open" | "closed";
                export type FreshReturnVector = "open" | "closed";
                export type InnerIsolationVector = "open" | "closed";
                export type CleanOverwriteVector = "open" | "closed";
                export const capturedWrite =
                  (value: CapturedWriteVector) => value;
                export const argumentWrite =
                  (value: ArgumentWriteVector) => value;
                export const freshReturn =
                  (value: FreshReturnVector) => value;
                export const innerIsolation =
                  (value: InnerIsolationVector) => value;
                export const cleanOverwrite =
                  (value: CleanOverwriteVector) => value;
                """
            ),
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const independent = {} as Atlas.AuthorityPresentation;
                function identity<T>(value: T): T {
                  return value;
                }
                function invoke<T>(value: T): T {
                  return identity(value);
                }
                function mutate(
                  target: { presentation: Atlas.AuthorityPresentation },
                  value: Atlas.AuthorityPresentation,
                ) {
                  target.presentation = value;
                }
                function fresh(value: Atlas.AuthorityPresentation) {
                  const local = { presentation: value };
                  return local;
                }
                export function Probe() {
                  let capturedPresentation = independent;
                  function setCaptured(value: Atlas.AuthorityPresentation) {
                    capturedPresentation = value;
                  }
                  setCaptured(Atlas.capturedWrite("closed") as unknown as
                    Atlas.AuthorityPresentation);

                  const argumentProps = { presentation: independent };
                  mutate(
                    argumentProps,
                    Atlas.argumentWrite("closed") as unknown as
                      Atlas.AuthorityPresentation,
                  );

                  const freshProps = fresh(
                    Atlas.freshReturn("closed") as unknown as
                      Atlas.AuthorityPresentation,
                  );

                  invoke(Atlas.innerIsolation("closed"));
                  const isolatedPresentation = invoke(independent);

                  const cleanProps = {
                    presentation: Atlas.cleanOverwrite("closed") as unknown as
                      Atlas.AuthorityPresentation,
                  };
                  mutate(cleanProps, independent);

                  return <>
                    <Atlas.AuthorityBadge
                      presentation={capturedPresentation}
                    />
                    <Atlas.AuthorityBadge {...argumentProps} />
                    <Atlas.AuthorityBadge {...freshProps} />
                    <Atlas.AuthorityBadge
                      presentation={isolatedPresentation}
                    />
                    <Atlas.AuthorityBadge {...cleanProps} />
                  </>;
                }
                """
            ),
        )

        expected = {
            "CapturedWriteVector",
            "ArgumentWriteVector",
            "FreshReturnVector",
        }
        self.assertEqual(expected, self._owner_names(scan))
        self.assertEqual(expected, self._sink_owner_names(scan, "presentation"))
        self.assertNotIn("InnerIsolationVector", self._owner_names(scan))
        self.assertNotIn("CleanOverwriteVector", self._owner_names(scan))
        self.assertIn(
            f"unauthorized_status_sink:{PROBE_PATH}:presentation", errors
        )

    def test_lifecycle_sinks_derive_from_resolved_atlas_component_props(
        self,
    ) -> None:
        errors, scan = self._validate(
            ts_source(
                """
                export { AuthorityBadge } from "./primitives/AuthorityBadge";
                export type { AuthorityPresentation } from
                  "./primitives/AuthorityBadge";
                export { Button } from "./primitives/Button";
                export { SegmentedControl } from
                  "./primitives/SegmentedControl";
                export type BadgeDirectVector = "open" | "closed";
                export type BadgeSpreadVector = "open" | "closed";
                export type ButtonDirectVector = "open" | "closed";
                export type ButtonSpreadVector = "open" | "closed";
                export type SegmentDirectVector = "open" | "closed";
                export type SegmentSpreadVector = "open" | "closed";
                export type LocalFakeVector = "open" | "closed";
                export const badgeDirect = (value: BadgeDirectVector) => value;
                export const badgeSpread = (value: BadgeSpreadVector) => value;
                export const buttonDirect =
                  (value: ButtonDirectVector) => value;
                export const buttonSpread =
                  (value: ButtonSpreadVector) => value;
                export const segmentDirect =
                  (value: SegmentDirectVector) => value;
                export const segmentSpread =
                  (value: SegmentSpreadVector) => value;
                export const localFake = (value: LocalFakeVector) => value;
                """
            ),
            ts_source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                function LocalControl({ disabled: _disabled }: {
                  disabled?: boolean;
                }) {
                  return <div />;
                }
                export function Probe() {
                  const badgeDirect = Atlas.badgeDirect("closed") as unknown as
                    Atlas.AuthorityPresentation;
                  const badgeSpread = Atlas.badgeSpread("closed") as unknown as
                    Atlas.AuthorityPresentation;
                  const buttonDirect = Atlas.buttonDirect("closed") === "closed";
                  const buttonSpread = Atlas.buttonSpread("closed") === "closed";
                  const segmentDirect =
                    Atlas.segmentDirect("closed") === "closed";
                  const segmentSpread =
                    Atlas.segmentSpread("closed") === "closed";
                  const localFake = Atlas.localFake("closed") === "closed";
                  return <>
                    <Atlas.AuthorityBadge presentation={badgeDirect} />
                    <Atlas.AuthorityBadge {...{ presentation: badgeSpread }} />
                    <Atlas.Button disabled={buttonDirect}>Review</Atlas.Button>
                    <Atlas.Button {...{ disabled: buttonSpread }}>
                      Review
                    </Atlas.Button>
                    <Atlas.SegmentedControl
                      value="a"
                      options={[{ value: "a", label: "A" }]}
                      onValueChange={() => undefined}
                      disabled={segmentDirect}
                    />
                    <Atlas.SegmentedControl
                      value="a"
                      options={[{ value: "a", label: "A" }]}
                      onValueChange={() => undefined}
                      {...{ disabled: segmentSpread }}
                    />
                    <LocalControl disabled={localFake} />
                  </>;
                }
                """
            ),
        )

        expected = {
            "BadgeDirectVector",
            "BadgeSpreadVector",
            "ButtonDirectVector",
            "ButtonSpreadVector",
            "SegmentDirectVector",
            "SegmentSpreadVector",
        }
        self.assertEqual(expected, self._owner_names(scan))
        self.assertNotIn("LocalFakeVector", self._owner_names(scan))
        self.assertEqual(
            {"BadgeDirectVector", "BadgeSpreadVector"},
            self._sink_owner_names(scan, "presentation"),
        )
        self.assertEqual(
            {
                "ButtonDirectVector",
                "ButtonSpreadVector",
                "SegmentDirectVector",
                "SegmentSpreadVector",
            },
            self._sink_owner_names(scan, "disabled"),
        )
        self.assertIn(
            f"unauthorized_status_sink:{PROBE_PATH}:disabled", errors
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
