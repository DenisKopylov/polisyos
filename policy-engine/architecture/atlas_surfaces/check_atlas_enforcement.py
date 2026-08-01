#!/usr/bin/env python3
"""Run the shared Atlas semantic engine and reject unauthorized status owners."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from textwrap import dedent
from typing import Any

ATLAS_DIR = Path(__file__).resolve().parent
STATUS_CHECKER_PATH = ATLAS_DIR / "check_status_retirement_inventory.py"

_SPEC = importlib.util.spec_from_file_location(
    "status_retirement_checker", STATUS_CHECKER_PATH
)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import bootstrap guard
    raise RuntimeError(f"Unable to import status checker from {STATUS_CHECKER_PATH}")
status_checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(status_checker)


def _finding_name(finding: Mapping[str, Any]) -> str:
    return str(
        finding.get("declarationName")
        or finding.get("fieldName")
        or "unknown"
    )


def _enforcement_errors(scan: Mapping[str, Any]) -> list[str]:
    """Translate additive semantic-engine findings into stable lint diagnostics."""
    errors = [
        "unauthorized_status_owner:"
        + str(finding.get("path", "unknown"))
        + ":"
        + _finding_name(finding)
        for finding in scan.get("unauthorizedStatusOwners", [])
        if isinstance(finding, Mapping)
    ]
    errors.extend(
        "unauthorized_status_sink:"
        + str(finding.get("path", "unknown"))
        + ":"
        + str(finding.get("sinkField", "unknown"))
        for finding in scan.get("unauthorizedStatusSinks", [])
        if isinstance(finding, Mapping)
    )
    errors.extend(
        "invalid_source_override:"
        + str(diagnostic.get("path", "unknown"))
        + ":"
        + str(diagnostic.get("line", 0))
        + ":TS"
        + str(diagnostic.get("code", "unknown"))
        for diagnostic in scan.get("overrideDiagnostics", [])
        if isinstance(diagnostic, Mapping)
    )
    return sorted(set(errors))


def validate_enforcement(
    *, source_overrides: Mapping[str, str] | None = None
) -> tuple[list[str], dict[str, Any]]:
    """Return DS4 receipt errors plus additive cross-package owner findings.

    Args:
        source_overrides: Optional in-memory TypeScript sources for corruption
            witnesses.

    Returns:
        Stable enforcement diagnostics and the typed semantic scan result.
    """
    inventory = status_checker._load_json(status_checker.INVENTORY_PATH)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    scan = status_checker._scan(
        source_overrides,
        inventory=inventory,
        validate_override_diagnostics=source_overrides is not None,
    )
    errors = _enforcement_errors(scan)
    if source_overrides is None:
        errors.extend(
            status_checker.validate_inventory(
                inventory,
                debt,
                live_probes=True,
            )
        )
    return sorted(set(errors)), scan


def _corruption_probes() -> list[str]:
    escaped: list[str] = []
    package_path = "packages/atlas-ui/src/index.ts"
    sink_path = (
        "apps/runtime-dashboard/src/shared/lib/domain/"
        "packageOwnerCorruptionProbe.tsx"
    )

    def run(
        label: str,
        package_source: str,
        sink_source: str,
        *,
        expected_owners: set[str],
        expected_sinks: set[str],
        extra_sources: Mapping[str, str] | None = None,
    ) -> None:
        sources = {package_path: package_source, sink_path: sink_source}
        if extra_sources:
            sources.update(extra_sources)
        errors, scan = validate_enforcement(source_overrides=sources)
        owner_names = {
            _finding_name(finding)
            for finding in scan.get("unauthorizedStatusOwners", [])
            if isinstance(finding, Mapping)
        }
        sink_fields = {
            str(finding.get("sinkField"))
            for finding in scan.get("unauthorizedStatusSinks", [])
            if isinstance(finding, Mapping)
        }
        expected_errors = {
            *(
                f"unauthorized_status_owner:{package_path}:{owner}"
                for owner in expected_owners
            ),
            *(
                f"unauthorized_status_sink:{sink_path}:{field}"
                for field in expected_sinks
            ),
        }
        if (
            owner_names != expected_owners
            or sink_fields != expected_sinks
            or not expected_errors.issubset(errors)
        ):
            escaped.append(label)

    exports = (
        'export { AuthorityBadge } from "./primitives/AuthorityBadge";\n'
        'export type { AuthorityPresentation } from '
        '"./primitives/AuthorityBadge";\n'
        'export { Button } from "./primitives/Button";\n'
        'export { SegmentedControl } from "./primitives/SegmentedControl";\n'
    )
    source = lambda text: dedent(text).strip() + "\n"  # noqa: E731
    run(
        "name-independent-reachable-owners",
        exports
        + 'export type UnusedDecisionStatus = "ready" | "blocked";\n'
        + 'export type DecisionPosture = "ready" | "blocked";\n'
        + 'export type OutcomeMode = "ready" | "blocked";\n'
        + 'export type ReviewPhase = "ready" | "blocked";\n'
        + "export const posture = (value: DecisionPosture) => value;\n"
        + "export const mode = (value: OutcomeMode) => value;\n"
        + "export const phase = (value: ReviewPhase) => value;\n",
        'import * as Atlas from "@polisyos/atlas-ui";\n'
        + "const cast = (value: unknown) => "
        + "value as Atlas.AuthorityPresentation;\n"
        + "export function Probe() { return <>\n"
        + '  <Atlas.AuthorityBadge presentation={cast(Atlas.posture("ready"))} />\n'
        + '  <Atlas.AuthorityBadge presentation={cast(Atlas.mode("ready"))} />\n'
        + '  <Atlas.AuthorityBadge presentation={cast(Atlas.phase("ready"))} />\n'
        + "</>; }\n",
        expected_owners={"DecisionPosture", "OutcomeMode", "ReviewPhase"},
        expected_sinks={"presentation"},
    )

    fake_path = "packages/runtime-api-client/fake.ts"
    run(
        "exact-generated-artifact-provenance",
        'import type { VerificationMetadata } from '
        '"@polisyos/runtime-api-client";\n'
        + 'import type { FakeGenerated } from "../../runtime-api-client/fake";\n'
        + exports
        + "export type Governed = "
        + 'VerificationMetadata["verification_status"];\n'
        + "export type PrefixLookalike = FakeGenerated[\"outcome\"];\n"
        + "export const fake = (value: PrefixLookalike) => value;\n",
        'import * as Atlas from "@polisyos/atlas-ui";\n'
        + "export function Probe() {\n"
        + '  const value = Atlas.fake("ready");\n'
        + "  return <Atlas.AuthorityBadge presentation={value as unknown as "
        + "Atlas.AuthorityPresentation} />;\n"
        + "}\n",
        expected_owners={"PrefixLookalike"},
        expected_sinks={"presentation"},
        extra_sources={
            fake_path: (
                "export interface FakeGenerated {\n"
                '  outcome: "ready" | "blocked";\n'
                "}\n"
            )
        },
    )

    run(
        "field-and-call-sensitive-benign-controls",
        exports
        + 'export type ReviewPhase = "ready" | "blocked";\n'
        + "export const preserve = (value: ReviewPhase) => value;\n",
        'import * as Atlas from "@polisyos/atlas-ui";\n'
        + "const independent = {} as Atlas.AuthorityPresentation;\n"
        + "function discard(_value: unknown) { return independent; }\n"
        + "export function Probe() {\n"
        + '  const owner = Atlas.preserve("ready");\n'
        + "  const carrier = { owner, presentation: discard(owner) };\n"
        + "  return <Atlas.AuthorityBadge "
        + "presentation={carrier.presentation} />;\n"
        + "}\n",
        expected_owners=set(),
        expected_sinks=set(),
    )

    run(
        "carrier-and-lifecycle-provenance",
        exports
        + 'export type ReviewPhase = "ready" | "blocked";\n'
        + "export const preserve = (value: ReviewPhase) => value;\n",
        'import * as Atlas from "@polisyos/atlas-ui";\n'
        + "function propsFor(value: Atlas.ReviewPhase) {\n"
        + "  const presentation = "
        + "value as unknown as Atlas.AuthorityPresentation;\n"
        + "  return { presentation };\n"
        + "}\n"
        + "export function Probe() {\n"
        + '  const owner = Atlas.preserve("ready");\n'
        + '  const blocked = owner === "blocked";\n'
        + "  return <>\n"
        + "    <Atlas.AuthorityBadge {...propsFor(owner)} />\n"
        + "    <Atlas.Button disabled={blocked} "
        + 'aria-disabled={blocked}>Review</Atlas.Button>\n'
        + "  </>;\n"
        + "}\n",
        expected_owners={"ReviewPhase"},
        expected_sinks={"presentation", "disabled", "aria-disabled"},
    )

    run(
        "mixed-generated-local-branch",
        source(
            """
            import type { VerificationMetadata } from
              "@polisyos/runtime-api-client";
            export { AuthorityBadge } from "./primitives/AuthorityBadge";
            export type { AuthorityPresentation } from
              "./primitives/AuthorityBadge";
            export type PolicyDialect =
              VerificationMetadata["verification_status"] | "atlas_local";
            export const preserve = (value: PolicyDialect) => value;
            """
        ),
        source(
            """
            import * as Atlas from "@polisyos/atlas-ui";
            export function Probe() {
              const presentation = Atlas.preserve("atlas_local") as unknown as
                Atlas.AuthorityPresentation;
              return <Atlas.AuthorityBadge presentation={presentation} />;
            }
            """
        ),
        expected_owners={"PolicyDialect"},
        expected_sinks={"presentation"},
    )

    run(
        "program-point-identity-and-overwrite",
        exports
        + 'export type IdentityVector = "open" | "closed";\n'
        + 'export type OverwrittenVector = "open" | "closed";\n'
        + "export const identity = (value: IdentityVector) => value;\n"
        + "export const overwritten = (value: OverwrittenVector) => value;\n",
        source(
            """
            import * as Atlas from "@polisyos/atlas-ui";
            const independent = {} as Atlas.AuthorityPresentation;
            export function Probe() {
              const props = { presentation: independent };
              const alias = props;
              alias["presentation"] = Atlas.identity("closed") as unknown as
                Atlas.AuthorityPresentation;
              const overwritten = Atlas.overwritten("closed") as unknown as
                Atlas.AuthorityPresentation;
              return <>
                <Atlas.AuthorityBadge {...props} />
                <Atlas.AuthorityBadge
                  {...{ presentation: overwritten }}
                  presentation={independent}
                />
              </>;
            }
            """
        ),
        expected_owners={"IdentityVector"},
        expected_sinks={"presentation"},
    )

    run(
        "cfg-closure-higher-order-recursive",
        exports
        + 'export type ClosureVector = "open" | "closed";\n'
        + 'export type ApplyVector = "open" | "closed";\n'
        + 'export type RecursiveVector = "open" | "closed";\n'
        + 'export type ArgumentVector = "open" | "closed";\n'
        + 'export type FreshVector = "open" | "closed";\n'
        + 'export type IsolationVector = "open" | "closed";\n'
        + "export const closure = (value: ClosureVector) => value;\n"
        + "export const applyOwner = (value: ApplyVector) => value;\n"
        + "export const recursive = (value: RecursiveVector) => value;\n"
        + "export const argument = (value: ArgumentVector) => value;\n"
        + "export const fresh = (value: FreshVector) => value;\n"
        + "export const isolation = (value: IsolationVector) => value;\n",
        source(
            """
            import * as Atlas from "@polisyos/atlas-ui";
            const independent = {} as Atlas.AuthorityPresentation;
            type Box = { next?: Box; value?: unknown };
            function apply<T, U>(fn: (value: T) => U, value: T): U {
              return fn(value);
            }
            function carry(value: unknown, depth: number): Box {
              if (depth <= 0) return { value };
              return { next: carry(value, depth - 1) };
            }
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
              return { presentation: value };
            }
            export function Probe() {
              let closurePresentation = independent;
              function setOwner() {
                closurePresentation = Atlas.closure("closed") as unknown as
                  Atlas.AuthorityPresentation;
              }
              setOwner();
              const applyPresentation = apply(
                (value) => value as unknown as Atlas.AuthorityPresentation,
                Atlas.applyOwner("closed"),
              );
              const box = carry(Atlas.recursive("closed"), 8);
              const recursivePresentation = box.next!.next!.next!.next!.next!
                .next!.next!.next!.value as Atlas.AuthorityPresentation;
              const argumentProps = { presentation: independent };
              mutate(
                argumentProps,
                Atlas.argument("closed") as unknown as
                  Atlas.AuthorityPresentation,
              );
              const freshProps = fresh(
                Atlas.fresh("closed") as unknown as
                  Atlas.AuthorityPresentation,
              );
              invoke(Atlas.isolation("closed"));
              const isolatedPresentation = invoke(independent);
              return <>
                <Atlas.AuthorityBadge presentation={closurePresentation} />
                <Atlas.AuthorityBadge presentation={applyPresentation} />
                <Atlas.AuthorityBadge presentation={recursivePresentation} />
                <Atlas.AuthorityBadge {...argumentProps} />
                <Atlas.AuthorityBadge {...freshProps} />
                <Atlas.AuthorityBadge presentation={isolatedPresentation} />
              </>;
            }
            """
        ),
        expected_owners={
            "ClosureVector",
            "ApplyVector",
            "RecursiveVector",
            "ArgumentVector",
            "FreshVector",
        },
        expected_sinks={"presentation"},
    )

    run(
        "resolved-sibling-lifecycle",
        exports
        + 'export type SegmentVector = "open" | "closed";\n'
        + 'export type LocalVector = "open" | "closed";\n'
        + "export const segment = (value: SegmentVector) => value;\n"
        + "export const local = (value: LocalVector) => value;\n",
        source(
            """
            import * as Atlas from "@polisyos/atlas-ui";
            function LocalControl({ disabled: _disabled }: {
              disabled?: boolean;
            }) {
              return <div />;
            }
            export function Probe() {
              const segment = Atlas.segment("closed") === "closed";
              const local = Atlas.local("closed") === "closed";
              return <>
                <Atlas.SegmentedControl
                  value="a"
                  options={[{ value: "a", label: "A" }]}
                  onValueChange={() => undefined}
                  disabled={segment}
                />
                <LocalControl disabled={local} />
              </>;
            }
            """
        ),
        expected_owners={"SegmentVector"},
        expected_sinks={"disabled"},
    )

    invalid_errors, invalid_scan = validate_enforcement(
        source_overrides={
            package_path: (
                'export { AuthorityBadge } from "./primitives/AuthorityBadge";\n'
                'export type { AuthorityPresentation } from '
                '"./primitives/AuthorityBadge";\n'
            ),
            sink_path: source(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const props: {
                  presentation?: Atlas.AuthorityPresentation;
                } = {};
                export const Probe = () =>
                  <Atlas.AuthorityBadge {...props} />;
                """
            ),
        }
    )
    invalid_diagnostics = invalid_scan.get("overrideDiagnostics", [])
    if (
        len(invalid_diagnostics) != 1
        or invalid_diagnostics[0].get("code") != 2322
        or not any(error.endswith(":TS2322") for error in invalid_errors)
    ):
        escaped.append("invalid-override-diagnostic")

    # Keep the real generated owner and responsive interaction vocabulary benign.
    errors, scan = validate_enforcement(
        source_overrides={
            package_path: (
                'import type { VerificationMetadata } from '
                '"@polisyos/runtime-api-client";\n'
                + exports
                + 'export type ResponsiveInteractionState = "compact" | "expanded";\n'
                "export type GeneratedOwnerMarker = "
                'VerificationMetadata["dispute_status"];\n'
            ),
            sink_path: (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                + "export function Probe() { return <div />; }\n"
            ),
        }
    )
    if errors or scan.get("unauthorizedStatusOwners") or scan.get(
        "unauthorizedStatusSinks"
    ):
        escaped.append("generated-and-responsive-benign-controls")
    return escaped


def _summary(scan: Mapping[str, Any]) -> dict[str, Any]:
    inventory = status_checker._load_json(status_checker.INVENTORY_PATH)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    status_summary = status_checker._summary(inventory, debt)
    denominators = scan.get("sourceDenominators", {})
    return {
        "atlas_ui_production_sources": denominators.get("atlasUiProduction"),
        "current_authored_statuses": status_summary["current_authored"],
        "ds1_status_rows": status_summary["ds1_rows"],
        "unauthorized_status_owners": len(
            scan.get("unauthorizedStatusOwners", [])
        ),
        "unauthorized_status_sinks": len(
            scan.get("unauthorizedStatusSinks", [])
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the live enforcement gate and optional corruption witnesses.

    Args:
        argv: Optional command-line arguments.

    Returns:
        Zero when every live and requested corruption check passes.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--corruption-probes", action="store_true")
    args = parser.parse_args(argv)
    errors, scan = validate_enforcement()
    if errors:
        for error in errors:
            sys.stderr.write(error + "\n")
        return 1
    if args.corruption_probes:
        escaped = _corruption_probes()
        if escaped:
            sys.stderr.write(
                "corruption probes escaped: " + ", ".join(escaped) + "\n"
            )
            return 1
        sys.stdout.write("Atlas enforcement corruption probes: PASS\n")
    sys.stdout.write(json.dumps(_summary(scan), indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
