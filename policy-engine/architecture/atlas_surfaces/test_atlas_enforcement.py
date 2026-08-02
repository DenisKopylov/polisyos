"""Behavioral tests for the retained DS5 enforcement core."""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
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
AUTHORITY_BADGE_PATH = "packages/atlas-ui/src/primitives/AuthorityBadge.tsx"
EVIDENCE_TYPES_PATH = "packages/atlas-ui/src/primitives/evidenceTypes.ts"
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

    def test_real_illegal_edges_fail_custom_and_dependency_engines(self) -> None:
        errors, receipt = checker._architecture_recurrence_errors()

        self.assertEqual([], errors)
        self.assertEqual(
            {
                "app-no-feature-internals",
                "app-state-no-app-providers",
                "shared-no-app-or-features",
            },
            set(receipt["corruption"]["dashboard-custom"]["violation_rules"]),
        )
        self.assertEqual(
            {
                "app-no-feature-internals",
                "no-circular",
                "shared-no-app-or-features",
            },
            set(receipt["corruption"]["dependency-cruiser"]["violation_rules"]),
        )
        self.assertEqual(
            ["atlas-forbidden-import"],
            receipt["corruption"]["atlas-ui"]["violation_rules"],
        )
        self.assertEqual(
            {
                "atlas-ui": 3,
                "dashboard-custom": 11,
                "dependency-cruiser": 11,
            },
            {
                engine_id: facts["source_files"]
                for engine_id, facts in receipt["corruption"].items()
            },
        )
        self.assertEqual(
            [],
            [
                engine_id
                for engine_id, facts in receipt["benign"].items()
                if facts.get("violation_rules", facts.get("violations"))
                or facts["return_code"] != 0
            ],
        )

    def test_architecture_receipts_reject_malformed_consumed_fields(self) -> None:
        errors, _facts = checker._architecture_packet_facts(
            {
                "dashboard-custom": {
                    "producer": "runtime-dashboard-custom-import-boundary",
                    "returnCode": 0,
                    "sourceFiles": "not-a-count",
                    "violations": [],
                },
                "dependency-cruiser": {
                    "returnCode": 0,
                    "modules": [{"source": "src/safe.ts", "dependencies": []}],
                    "summary": {"error": "zero", "violations": []},
                },
                "atlas-ui": {
                    "producer": "atlas-ui-import-boundary",
                    "returnCode": 0,
                    "sourceFiles": None,
                    "violations": [],
                },
            }
        )

        self.assertEqual(
            {
                "architecture_engine_reported_error_count_invalid:dependency-cruiser",
                "architecture_engine_source_count_invalid:atlas-ui",
                "architecture_engine_source_count_invalid:dashboard-custom",
            },
            set(errors),
        )

    def test_architecture_receipts_validate_each_consumed_field(self) -> None:
        valid_packets = {
            "dashboard-custom": {
                "producer": "runtime-dashboard-custom-import-boundary",
                "returnCode": 0,
                "sourceFiles": 1,
                "violations": [],
            },
            "dependency-cruiser": {
                "returnCode": 0,
                "modules": [{"source": "src/safe.ts", "dependencies": []}],
                "summary": {"error": 0, "violations": []},
            },
            "atlas-ui": {
                "producer": "atlas-ui-import-boundary",
                "returnCode": 0,
                "sourceFiles": 1,
                "violations": [],
            },
        }
        corruptions = {
            "custom-return": (
                ("dashboard-custom", "returnCode"),
                2,
                "architecture_engine_return_code_invalid:dashboard-custom",
            ),
            "custom-count": (
                ("dashboard-custom", "sourceFiles"),
                0,
                "architecture_engine_source_count_invalid:dashboard-custom",
            ),
            "custom-rule": (
                ("dashboard-custom", "violations"),
                [{}],
                "architecture_engine_violation_invalid:dashboard-custom",
            ),
            "dependency-return": (
                ("dependency-cruiser", "returnCode"),
                1,
                "architecture_engine_return_code_invalid:dependency-cruiser",
            ),
            "dependency-count": (
                ("dependency-cruiser", "modules"),
                [],
                "architecture_engine_source_count_invalid:dependency-cruiser",
            ),
            "dependency-edges": (
                ("dependency-cruiser", "modules", 0, "dependencies"),
                "not-a-list",
                "architecture_engine_module_invalid:dependency-cruiser",
            ),
            "dependency-source": (
                ("dependency-cruiser", "modules", 0, "source"),
                "",
                "architecture_engine_module_invalid:dependency-cruiser",
            ),
            "dependency-row": (
                ("dependency-cruiser", "modules", 0, "dependencies"),
                [None],
                "architecture_engine_dependency_invalid:dependency-cruiser",
            ),
            "dependency-resolved": (
                ("dependency-cruiser", "modules", 0, "dependencies"),
                [{"resolved": ""}],
                "architecture_engine_dependency_invalid:dependency-cruiser",
            ),
            "dependency-errors": (
                ("dependency-cruiser", "summary", "error"),
                -1,
                "architecture_engine_reported_error_count_invalid:dependency-cruiser",
            ),
            "dependency-rule": (
                ("dependency-cruiser", "summary", "violations"),
                [{"rule": {}}],
                "architecture_engine_violation_invalid:dependency-cruiser",
            ),
            "atlas-return": (
                ("atlas-ui", "returnCode"),
                2,
                "architecture_engine_return_code_invalid:atlas-ui",
            ),
            "atlas-count": (
                ("atlas-ui", "sourceFiles"),
                0,
                "architecture_engine_source_count_invalid:atlas-ui",
            ),
            "atlas-rule": (
                ("atlas-ui", "violations"),
                [{}],
                "architecture_engine_violation_invalid:atlas-ui",
            ),
        }

        for label, (path, value, expected_error) in corruptions.items():
            with self.subTest(label=label):
                packets = copy.deepcopy(valid_packets)
                target: Any = packets
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                errors, _facts = checker._architecture_packet_facts(packets)
                self.assertIn(expected_error, errors)

    def test_lint_enforcement_executes_the_three_architecture_engines(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            exit_code = checker.main(["--check"])

        self.assertEqual(0, exit_code)
        packet = json.loads(output.getvalue())
        receipt = packet["architecture_recurrence"]
        self.assertEqual(
            {"atlas-ui", "dashboard-custom", "dependency-cruiser"},
            set(receipt["live"]),
        )
        self.assertTrue(receipt["corruption_witnesses_rejected"])
        self.assertTrue(receipt["benign_graphs_accepted"])

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

    def test_authority_issuer_requires_generated_exhaustiveness_and_runtime_novelty(
        self,
    ) -> None:
        errors, scan = checker.validate_enforcement()
        facts = scan.get("authorityIssuerFacts")

        self.assertEqual([], errors)
        self.assertIsInstance(facts, dict)
        self.assertEqual([], checker._authority_issuer_errors(scan))
        self.assertEqual(2, len(facts["modules"]))
        self.assertEqual(3, len(facts["brands"]))
        self.assertEqual(5, len(facts["factories"]))
        self.assertEqual(3, len(facts["stores"]))
        self.assertEqual(3, len(facts["privateConstructors"]))
        self.assertEqual(
            {
                "createOpaqueAuthorityPresentation",
                "createOperatorProjectionPresentation",
            },
            set(facts["unrecognizedNeutralFactories"]),
        )

    def test_authority_issuer_corruptions_fail_closed(self) -> None:
        source = (checker.status_checker.REPO_ROOT / AUTHORITY_BADGE_PATH).read_text(
            encoding="utf-8"
        )
        package_source = (checker.status_checker.REPO_ROOT / PACKAGE_PATH).read_text(
            encoding="utf-8"
        )
        evidence_source = (checker.status_checker.REPO_ROOT / EVIDENCE_TYPES_PATH).read_text(
            encoding="utf-8"
        )
        corruptions = {
            "partial-generated-map": (
                source.replace(
                    'satisfies Record<OperatorProjectionLabel["state"], BadgeTone>;',
                    'satisfies Partial<Record<OperatorProjectionLabel["state"], BadgeTone>>;',
                    1,
                ),
                "authority_issuer_exhaustive_tone_map_drift",
            ),
            "exported-brand": (
                source.replace(
                    "const authorityPresentationBrand = Symbol(",
                    "export const authorityPresentationBrand = Symbol(",
                    1,
                ),
                "authority_issuer_brands_drift",
            ),
            "exported-constructor": (
                source.replace(
                    "function createPresentation(",
                    "export function createPresentation(",
                    1,
                ),
                "authority_issuer_factories_drift",
            ),
            "unfrozen-issued-value": (
                source.replace("return Object.freeze(issued);", "return issued;", 1),
                "authority_issuer_constructor_return_not_frozen:createPresentation",
            ),
            "runtime-novelty-upgrade": (
                source.replace(
                    'presentation: "unrecognized",',
                    'presentation: "recognized",',
                    1,
                ),
                "authority_issuer_runtime_novelty_drift",
            ),
            "exported-owner-vocabulary": (
                source.replace(
                    "const projectionStateTones = {",
                    "export const projectionStateTones = {",
                    1,
                ),
                "authority_issuer_exported_vocabulary",
            ),
            "caller-selected-tone": (
                source.replace(
                    "export function createOperatorBlockingCausePresentation(\n"
                    "  diagnostic: OperatorDiagnosticOwner,\n"
                    "): AuthorityPresentation {",
                    "export function createOperatorBlockingCausePresentation(\n"
                    "  diagnostic: OperatorDiagnosticOwner,\n"
                    '  callerTone: BadgeTone = "fail",\n'
                    "): AuthorityPresentation {",
                    1,
                ).replace('tone: "fail",', "tone: callerTone,", 1),
                "authority_issuer_factory_parameters_drift:createOperatorBlockingCausePresentation",
            ),
            "indirect-brand-export": (
                source.replace(
                    'const authorityPresentationBrand = Symbol("polisyos.authority-presentation");',
                    "const authorityPresentationBrand = "
                    'Symbol("polisyos.authority-presentation");\n'
                    "export { authorityPresentationBrand };",
                    1,
                ),
                "authority_issuer_brand_exported:authorityPresentationBrand",
            ),
            "shadowed-issuance-builtins": (
                source.replace(
                    'import type { FixtureAuthority } from "./evidenceTypes";',
                    'import type { FixtureAuthority } from "./evidenceTypes";\n\n'
                    "class WeakSet<Value extends object> {\n"
                    "  readonly #values = new globalThis.WeakSet<Value>();\n"
                    "  add(value: Value): this { this.#values.add(value); return this; }\n"
                    "  has(value: Value): boolean { return this.#values.has(value); }\n"
                    "}\n"
                    "class WeakMap<Key extends object, Value> {\n"
                    "  readonly #values = new globalThis.WeakMap<Key, Value>();\n"
                    "  set(key: Key, value: Value): this { "
                    "this.#values.set(key, value); return this; }\n"
                    "  get(key: Key): Value | undefined { return this.#values.get(key); }\n"
                    "}\n"
                    "const Object = {\n"
                    "  freeze: globalThis.Object.freeze,\n"
                    "  hasOwn: globalThis.Object.hasOwn,\n"
                    "};",
                    1,
                ),
                "authority_issuer_stores_drift",
            ),
            "dead-runtime-novelty-marker": (
                source.replace(
                    "  return createPresentation({\n"
                    "    authority,\n"
                    '    presentation: "unrecognized",\n'
                    '    source: "opaque_extension",\n'
                    '    tone: "neutral",\n'
                    "  });",
                    "  if (false) {\n"
                    "    return createPresentation({\n"
                    "      authority,\n"
                    '      presentation: "unrecognized",\n'
                    '      source: "opaque_extension",\n'
                    '      tone: "neutral",\n'
                    "    });\n"
                    "  }\n"
                    "  return createPresentation({\n"
                    "    authority,\n"
                    '    presentation: "recognized",\n'
                    '    source: "opaque_extension",\n'
                    '    tone: "ok",\n'
                    "  });",
                    1,
                ),
                "authority_issuer_factory_return_drift:createOpaqueAuthorityPresentation",
            ),
            "dead-return-with-live-indirect-issuance": (
                source.replace(
                    "  return createPresentation({\n"
                    "    authority,\n"
                    '    presentation: "unrecognized",\n'
                    '    source: "opaque_extension",\n'
                    '    tone: "neutral",\n'
                    "  });",
                    "  if (false) {\n"
                    "    return createPresentation({\n"
                    "      authority,\n"
                    '      presentation: "unrecognized",\n'
                    '      source: "opaque_extension",\n'
                    '      tone: "neutral",\n'
                    "    });\n"
                    "  }\n"
                    "  const upgraded = createPresentation({\n"
                    "    authority,\n"
                    '    presentation: "recognized",\n'
                    '    source: "opaque_extension",\n'
                    '    tone: "ok",\n'
                    "  });\n"
                    "  return upgraded;",
                    1,
                ),
                "authority_issuer_factory_call_shape_drift:createOpaqueAuthorityPresentation",
            ),
            "unused-membership-marker": (
                source.replace(
                    "  if (\n"
                    "    !(diagnostic.projection_labels as readonly unknown[] | "
                    "undefined)?.includes(\n"
                    "      item,\n"
                    "    )\n"
                    "  ) {\n"
                    "    throw new TypeError(\n"
                    '      "projection label must be a member of the generated owner diagnostic",\n'
                    "    );\n"
                    "  }",
                    "  (diagnostic.projection_labels as readonly unknown[] | undefined)"
                    "?.includes(item);",
                    1,
                ),
                "authority_issuer_owner_membership_drift",
            ),
            "dead-membership-marker": (
                source.replace(
                    "  if (\n"
                    "    !(diagnostic.projection_labels as readonly unknown[] | "
                    "undefined)?.includes(\n"
                    "      item,\n"
                    "    )\n"
                    "  ) {\n"
                    "    throw new TypeError(\n"
                    '      "projection label must be a member of the generated owner diagnostic",\n'
                    "    );\n"
                    "  }",
                    "  if (false) {\n"
                    "    if (\n"
                    "      !(\n"
                    "        diagnostic.projection_labels as readonly unknown[] | undefined\n"
                    "      )?.includes(item)\n"
                    "    ) {\n"
                    "      throw new TypeError(\n"
                    '        "projection label must be a member of the generated '
                    'owner diagnostic",\n'
                    "      );\n"
                    "    }\n"
                    "  }",
                    1,
                ),
                "authority_issuer_owner_membership_drift",
            ),
            "rebound-owner-membership": (
                source.replace(
                    "diagnostic.projection_labels as readonly unknown[] | undefined",
                    "[item] as readonly unknown[] | undefined",
                    1,
                ),
                "authority_issuer_owner_membership_drift",
            ),
            "missing-parity-invocation": (
                source.replace(
                    "assertProjectionVocabularyParity(true, true);\n",
                    "",
                    1,
                ),
                "authority_issuer_projection_parity_drift",
            ),
            "dead-parity-invocation": (
                source.replace(
                    "assertProjectionVocabularyParity(true, true);",
                    "if (false) {\n  assertProjectionVocabularyParity(true, true);\n}",
                    1,
                ),
                "authority_issuer_projection_parity_drift",
            ),
            "hardcoded-parity-predicate": (
                source.replace(
                    "type IsExact<Left, Right> =\n"
                    "  (<Value>() => Value extends Left ? 1 : 2) extends <\n"
                    "    Value,\n"
                    "  >() => Value extends Right ? 1 : 2\n"
                    "    ? (<Value>() => Value extends Right ? 1 : 2) extends <\n"
                    "        Value,\n"
                    "      >() => Value extends Left ? 1 : 2\n"
                    "      ? true\n"
                    "      : false\n"
                    "    : false;",
                    "type IsExact<Left, Right> = true;",
                    1,
                ),
                "authority_issuer_projection_parity_drift",
            ),
            "untyped-owner-vocabulary-reconstruction": (
                source.replace(
                    "type OperatorDiagnosticOwner =",
                    "export const leakedOwnerStates = [\n"
                    '  "approved", "blocked", "contested", "draft",\n'
                    '  "projected", "projection_only", "publishable",\n'
                    '  "published_blocked", "readiness_closed", "redacted",\n'
                    '  "rejected", "stale",\n'
                    "];\n\n"
                    "type OperatorDiagnosticOwner =",
                    1,
                ),
                "authority_issuer_exported_vocabulary",
            ),
            "untyped-owner-vocabulary-subset": (
                source.replace(
                    "type OperatorDiagnosticOwner =",
                    'export const leakedOwnerSubset = ["approved", "blocked"];\n\n'
                    "type OperatorDiagnosticOwner =",
                    1,
                ),
                "authority_issuer_exported_vocabulary",
            ),
            "aliased-owner-vocabulary-reconstruction": (
                source.replace(
                    'satisfies Record<OperatorProjectionLabel["state"], BadgeTone>;',
                    'satisfies Record<OperatorProjectionLabel["state"], BadgeTone>;\n'
                    "export const leakedOwnerStates = projectionStateTones;",
                    1,
                ),
                "authority_issuer_exported_vocabulary",
            ),
        }
        for label, (corrupted_source, expected_error) in corruptions.items():
            with self.subTest(label=label):
                errors, scan = checker.validate_enforcement(
                    source_overrides={
                        PACKAGE_PATH: package_source,
                        AUTHORITY_BADGE_PATH: corrupted_source,
                    },
                    enforce_authority_escapes=False,
                )
                self.assertEqual([], errors)
                issuer_errors = checker._authority_issuer_errors(scan)
                self.assertTrue(
                    any(
                        error == expected_error or error.startswith(expected_error + ":")
                        for error in issuer_errors
                    ),
                    issuer_errors,
                )

        evidence_corruptions = {
            "unused-governed-membership-marker": (
                evidence_source.replace(
                    "  if (!packet.authoritative_for.includes(authorityPurpose)) {\n"
                    "    throw new TypeError(\n"
                    '      "authority purpose is not declared by the owner packet",\n'
                    "    );\n"
                    "  }",
                    "  packet.authoritative_for.includes(authorityPurpose);",
                    1,
                ),
                "authority_issuer_owner_membership_drift",
            ),
            "shadowed-weakmap-and-freeze": (
                evidence_source.replace(
                    '} from "@polisyos/runtime-api-client";',
                    '} from "@polisyos/runtime-api-client";\n\n'
                    "class WeakMap<Key extends object, Value> {\n"
                    "  readonly #values = new globalThis.WeakMap<Key, Value>();\n"
                    "  set(key: Key, value: Value): this { "
                    "this.#values.set(key, value); return this; }\n"
                    "  get(key: Key): Value | undefined { return this.#values.get(key); }\n"
                    "}\n"
                    "const Object = {\n"
                    "  freeze: globalThis.Object.freeze,\n"
                    "  hasOwn: globalThis.Object.hasOwn,\n"
                    "};",
                    1,
                ),
                "authority_issuer_stores_drift",
            ),
        }
        for label, (corrupted_source, expected_error) in evidence_corruptions.items():
            with self.subTest(label=label):
                errors, scan = checker.validate_enforcement(
                    source_overrides={
                        PACKAGE_PATH: package_source,
                        EVIDENCE_TYPES_PATH: corrupted_source,
                    },
                    enforce_authority_escapes=False,
                )
                self.assertEqual([], errors)
                issuer_errors = checker._authority_issuer_errors(scan)
                self.assertTrue(
                    any(
                        error == expected_error or error.startswith(expected_error + ":")
                        for error in issuer_errors
                    ),
                    issuer_errors,
                )

        benign_source = source.replace(
            "type OperatorDiagnosticOwner =",
            'export const AUTHORITY_BADGE_TEST_ID = "authority-badge";\n\n'
            "type OperatorDiagnosticOwner =",
            1,
        )
        errors, benign_scan = checker.validate_enforcement(
            source_overrides={
                PACKAGE_PATH: package_source,
                AUTHORITY_BADGE_PATH: benign_source,
            },
            enforce_authority_escapes=False,
        )
        self.assertEqual([], errors)
        self.assertEqual([], checker._authority_issuer_errors(benign_scan))

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
