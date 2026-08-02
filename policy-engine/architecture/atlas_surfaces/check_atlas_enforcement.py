#!/usr/bin/env python3
"""Validate the sound DS5 enforcement core."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from textwrap import dedent
from typing import Any, Literal, NamedTuple

ATLAS_DIR = Path(__file__).resolve().parent
STATUS_CHECKER_PATH = ATLAS_DIR / "check_status_retirement_inventory.py"
DISPOSITION_CHECKER_PATH = ATLAS_DIR / "check_frontend_disposition_register.py"

_SPEC = importlib.util.spec_from_file_location("status_retirement_checker", STATUS_CHECKER_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to import status checker from {STATUS_CHECKER_PATH}")
status_checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(status_checker)

_DISPOSITION_SPEC = importlib.util.spec_from_file_location(
    "atlas_enforcement_disposition_checker", DISPOSITION_CHECKER_PATH
)
if _DISPOSITION_SPEC is None or _DISPOSITION_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"Unable to import disposition checker from {DISPOSITION_CHECKER_PATH}")
disposition_checker = importlib.util.module_from_spec(_DISPOSITION_SPEC)
_DISPOSITION_SPEC.loader.exec_module(disposition_checker)

AuthorityEscapeConstruct = Literal[
    "as_assertion",
    "type_assertion",
    "explicit_any",
    "ts_ignore",
    "ts_expect_error",
    "ts_nocheck",
    "satisfies",
]


class AuthorityEscapeExemption(NamedTuple):
    """Exact, owned exception to the bounded authority-path syntax rule."""

    exemption_id: str
    path: str
    line: int
    column: int
    construct: AuthorityEscapeConstruct
    target: str
    site_sha256: str
    owner: str
    reason: str


_ISSUER_ERASURE_REASON = (
    "Runtime-erased generated owner inspection is narrowed only after local "
    "shape or membership checks; the assertion neither targets nor issues a brand."
)
_RUNTIME_NEGATIVE_REASON = (
    "The runtime negative deliberately models a JavaScript value after type erasure; "
    "the exact assertion is confined to rejection or novelty behavior."
)
_STATIC_OWNERSHIP_REASON = (
    "Literal preservation serves the static primitive-ownership census only; "
    "the table neither targets an authority brand nor reaches a presentation sink."
)


def _escape(
    exemption_id: str,
    path: str,
    line: int,
    column: int,
    construct: AuthorityEscapeConstruct,
    target: str,
    site_sha256: str,
    owner: str,
    reason: str,
) -> AuthorityEscapeExemption:
    return AuthorityEscapeExemption(
        exemption_id,
        path,
        line,
        column,
        construct,
        target,
        site_sha256,
        owner,
        reason,
    )


AUTHORITY_ESCAPE_EXEMPTIONS: tuple[AuthorityEscapeExemption, ...] = (
    _escape(
        "issuer-authority-badge-owner-label-array",
        "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
        136,
        23,
        "as_assertion",
        "| readonly unknown[]\n    | undefined",
        "sha256:387dff7b2a5c7f06bd1586ef65cb7cd975118d8a021a48273b0677e322c69068",
        "DS5",
        _ISSUER_ERASURE_REASON,
    ),
    _escape(
        "issuer-authority-badge-runtime-label",
        "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
        144,
        23,
        "as_assertion",
        "{\n    authority?: unknown;\n    label?: unknown;\n    state?: unknown;\n  }",
        "sha256:2c5ad16863a03dd93cf0dc0a5d4f6a3f0bf9a1d6b86019194e41b721a8e22b13",
        "DS5",
        _ISSUER_ERASURE_REASON,
    ),
    _escape(
        "issuer-authority-badge-exhaustive-index",
        "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
        174,
        26,
        "as_assertion",
        "keyof typeof projectionStateTones",
        "sha256:3bafeebe683860825b3c6900970495e308bfdd096155ced0ad817888dcf015b8",
        "DS5",
        "Object.hasOwn proves the runtime key is present in the compile-time "
        "exhaustive generated-owner tone map; no brand is asserted.",
    ),
    _escape(
        "issuer-governed-purpose-payload-shape",
        "packages/atlas-ui/src/primitives/evidenceTypes.ts",
        69,
        10,
        "as_assertion",
        "{ fixture_authority?: unknown }",
        "sha256:adf83ddb012dfaea816f5dc1d1ad864941d305a85f2722cb4cce4a7d2fe6f003",
        "DS5",
        _ISSUER_ERASURE_REASON,
    ),
    _escape(
        "issuer-governed-purpose-fixture-payload",
        "packages/atlas-ui/src/primitives/evidenceTypes.ts",
        83,
        35,
        "as_assertion",
        "LegacyProvingGroundPayload",
        "sha256:65f9c1172517063f1bc66597fba513ec29661bfdc4d2cd060bb6b7b19a8fbea0",
        "DS5",
        "The discriminator and canonical fixture marker are checked immediately "
        "before the generated payload is passed to the private fixture issuer.",
    ),
    _escape(
        "test-authority-badge-forged-presentation",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        77,
        21,
        "as_assertion",
        "const",
        "sha256:23fa1dbe16420294c9df35fd9277adf24fbfee983aa605360b0e32a864fddadd",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-forged-tone",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        78,
        13,
        "as_assertion",
        "const",
        "sha256:fb976df9fefedeca7c78cf7511d57dfa1a4f4d7e5ea9d23923c1fb5cafee2c81",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-malformed-label-outer",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        80,
        23,
        "as_assertion",
        "RunOperatorProjectionStateLabel",
        "sha256:17a143ca3b81a016acfe638b2cc49458162967811a487f4f4897f16cf9f75a09",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-malformed-label-inner",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        80,
        23,
        "as_assertion",
        "unknown",
        "sha256:698a79719f7d1d67eb994f4cef6eb0356f9c198712c3951242889986d4b88a9d",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-malformed-owner",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        85,
        28,
        "as_assertion",
        "RunOperatorDiagnostic",
        "sha256:3a1847c542b8eff50d7fccda92b5f71ccd15e3fd10bb284ebc3268c4eb886a1a",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-novel-label-outer",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        107,
        23,
        "as_assertion",
        "RunOperatorProjectionStateLabel",
        "sha256:8e2d0d81a51b9bef0a4b149de3b00b00788fb673725d9d363c18b871eab5b18f",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-novel-label-inner",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        107,
        23,
        "as_assertion",
        "unknown",
        "sha256:8603ea50be860be72ad56e4fb4110206b056b57e92b7ac5564b7340aa22b02d5",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-authority-badge-novel-owner",
        "packages/atlas-ui/tests/AuthorityBadge.test.tsx",
        112,
        19,
        "as_assertion",
        "RunOperatorDiagnostic",
        "sha256:2645ab1dc363750112b186defbf155508f86c0de0e973c13c93fca018887bfaa",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-envelope-unavailable-outer",
        "packages/atlas-ui/tests/EnvelopeChip.test.tsx",
        30,
        25,
        "as_assertion",
        "typeof GOVERNED_PACKET",
        "sha256:fae74b3a99495e285cd8bd9d3d1419805cf540e9c9705ed2b746c3a3d88fd5b9",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-envelope-unavailable-inner",
        "packages/atlas-ui/tests/EnvelopeChip.test.tsx",
        30,
        25,
        "as_assertion",
        "unknown",
        "sha256:e4c7905ac012964b3dd9b0293a4d0ff820ff4d05aa9abe42877ef64404e83203",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-envelope-malformed-marker-outer",
        "packages/atlas-ui/tests/EnvelopeChip.test.tsx",
        66,
        23,
        "as_assertion",
        "typeof GOVERNED_PACKET",
        "sha256:6e591ce6fc41d1d0e011b6d3aaba24dd4fb91e1bdef0f6808aa926d678e842d9",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-envelope-malformed-marker-inner",
        "packages/atlas-ui/tests/EnvelopeChip.test.tsx",
        66,
        23,
        "as_assertion",
        "unknown",
        "sha256:09b1c9d01c9c298b41e27026ae137a02d9309e8a15d0cd4ae12e1466b9c4b924",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-envelope-missing-marker-outer",
        "packages/atlas-ui/tests/EnvelopeChip.test.tsx",
        78,
        21,
        "as_assertion",
        "typeof GOVERNED_PACKET",
        "sha256:b05306435f50633530db75bd7257f9c5d894c9ab72cbee9f09f2215e45a6987c",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-envelope-missing-marker-inner",
        "packages/atlas-ui/tests/EnvelopeChip.test.tsx",
        78,
        21,
        "as_assertion",
        "unknown",
        "sha256:89e184e190abaa8f2f9cf8c140d3567cfbd88fc3e04de98ede331aa1b8589fea",
        "DS5",
        _RUNTIME_NEGATIVE_REASON,
    ),
    _escape(
        "test-owner-foundation-families",
        "packages/atlas-ui/tests/oneOwner.test.ts",
        9,
        29,
        "as_assertion",
        "const",
        "sha256:7c1fdd6eac1ab7b66321406e476a8b6ab46ffff61b745171a85f466d26388f35",
        "team-design",
        _STATIC_OWNERSHIP_REASON,
    ),
    _escape(
        "test-owner-form-families",
        "packages/atlas-ui/tests/oneOwner.test.ts",
        36,
        23,
        "as_assertion",
        "const",
        "sha256:edaa52d1586a646c932f38fe036624967d30ec66c54df87a35a54e6e2fbf0786",
        "team-design",
        _STATIC_OWNERSHIP_REASON,
    ),
    _escape(
        "test-owner-overlay-families",
        "packages/atlas-ui/tests/oneOwner.test.ts",
        49,
        26,
        "as_assertion",
        "const",
        "sha256:3292124b28dcd885824eab489a8c0be3862b2abeeaeb5e37b451477d01acfb26",
        "team-design",
        _STATIC_OWNERSHIP_REASON,
    ),
    _escape(
        "test-owner-evidence-families",
        "packages/atlas-ui/tests/oneOwner.test.ts",
        77,
        27,
        "as_assertion",
        "const",
        "sha256:49d79202f7f2324f05e9574b0fd402b600dbbcee63df10b95d1632424ad8abb0",
        "team-design",
        _STATIC_OWNERSHIP_REASON,
    ),
    _escape(
        "test-owner-compound-families",
        "packages/atlas-ui/tests/oneOwner.test.ts",
        83,
        27,
        "as_assertion",
        "const",
        "sha256:7902d8d29a84ae1a92c94c4f61af15385d3e13049e545a05a9f5c4dcab060272",
        "team-design",
        _STATIC_OWNERSHIP_REASON,
    ),
    _escape(
        "test-owner-pattern-families",
        "packages/atlas-ui/tests/oneOwner.test.ts",
        89,
        26,
        "as_assertion",
        "const",
        "sha256:4c2be7bde77780431acb01c667fde81f37f24d4c1fba491137a9292e4e8fdb88",
        "team-design",
        _STATIC_OWNERSHIP_REASON,
    ),
    _escape(
        "story-meta-framework-conformance",
        "apps/runtime-dashboard/src/shared/ui/evidence/EvidencePrimitives.stories.tsx",
        163,
        14,
        "satisfies",
        "Meta",
        "sha256:0122b0001de5923a754c73c515d92a65d568632c717db250b70f3f7ab867cba5",
        "team-design",
        "Storybook metadata conformance is unrelated to authority and the target "
        "resolves to no private brand; framework types expose intentional unknown slots.",
    ),
)
AUTHORITY_PATH_EXPECTED_COUNT = 15
AUTHORITY_GOVERNANCE_OBJECTS = (
    "EVIDENCE_FAMILIES",
    "EXPECTED_RUNTIME_EXPORTS",
)


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


def _authority_path_descriptors() -> list[dict[str, str]]:
    """Return the two declaration-anchored branded authority props."""
    return [
        {
            "descriptorId": descriptor_id,
            "component": str(spec["component"]),
            "componentDeclarationPath": str(spec["component_declaration_path"]),
            "prop": str(spec["prop"]),
        }
        for descriptor_id, spec in sorted(
            disposition_checker.AUTHORITY_PROP_CLASSIFICATIONS.items()
        )
        if str(spec["classification"]).startswith("branded:")
    ]


def _enforcement_scan(
    source_overrides: Mapping[str, str] | None,
    *,
    inventory: Mapping[str, Any],
    validate_override_diagnostics: bool,
) -> dict[str, Any]:
    """Run the shared scanner with the bounded C01a/C01b descriptors."""
    request: dict[str, Any] = {}
    if source_overrides is not None:
        request["sourceOverrides"] = dict(sorted(source_overrides.items()))
        if validate_override_diagnostics:
            request["validateOverrideDiagnostics"] = True
    request["authorityPathDescriptors"] = _authority_path_descriptors()
    request["authorityGovernanceObjects"] = list(AUTHORITY_GOVERNANCE_OBJECTS)
    request["authorityPropDescriptors"] = (
        disposition_checker._authority_prop_descriptors() if source_overrides is None else []
    )
    request["protectedDefinitions"] = status_checker._protected_semantic_definitions(inventory)
    generated = inventory["sources"]["generated_client"]
    request["generatedDefinitionPaths"] = sorted(
        {str(generated["canonical_path"]), str(generated["types_path"])}
    )
    scan = status_checker._scan_json(json.dumps(request, sort_keys=True, separators=(",", ":")))
    for key in ("authorityPathFiles", "authorityEscapeSites"):
        if not isinstance(scan.get(key), list):
            raise RuntimeError(f"status TypeScript scan returned invalid {key}")
    return scan


def _escape_identity(value: Mapping[str, Any] | AuthorityEscapeExemption) -> tuple[Any, ...]:
    getter = (
        (lambda field: getattr(value, field))
        if isinstance(value, AuthorityEscapeExemption)
        else (lambda field: value.get(field))
    )
    return tuple(
        getter(field)
        for field in (
            "path",
            "line",
            "column",
            "construct",
            "target",
            "site_sha256" if isinstance(value, AuthorityEscapeExemption) else "siteSha256",
        )
    )


def _authority_escape_errors(
    scan: Mapping[str, Any],
    *,
    exemptions: Sequence[AuthorityEscapeExemption] = AUTHORITY_ESCAPE_EXEMPTIONS,
    enforce_denominator: bool = True,
) -> list[str]:
    """Validate local escape syntax; this deliberately performs no value flow."""
    errors: list[str] = []
    paths = scan.get("authorityPathFiles", [])
    sites = scan.get("authorityEscapeSites", [])
    if not isinstance(paths, list) or not isinstance(sites, list):
        return ["authority_escape_scan_invalid"]
    path_names = {
        str(row.get("path"))
        for row in paths
        if isinstance(row, Mapping) and isinstance(row.get("path"), str)
    }
    if len(path_names) != len(paths):
        errors.append("authority_escape_path_census_duplicate_or_invalid")
    if enforce_denominator and len(path_names) != AUTHORITY_PATH_EXPECTED_COUNT:
        errors.append(
            "authority_escape_path_denominator_drift:"
            f"expected={AUTHORITY_PATH_EXPECTED_COUNT}:actual={len(path_names)}"
        )

    allowed_constructs = {
        "as_assertion",
        "type_assertion",
        "explicit_any",
        "ts_ignore",
        "ts_expect_error",
        "ts_nocheck",
        "satisfies",
    }
    exemption_by_identity: dict[tuple[Any, ...], AuthorityEscapeExemption] = {}
    exemption_ids: set[str] = set()
    for exemption in exemptions:
        if exemption.exemption_id in exemption_ids:
            errors.append(f"authority_escape_exemption_duplicate:{exemption.exemption_id}")
        exemption_ids.add(exemption.exemption_id)
        if exemption.construct not in allowed_constructs:
            errors.append("authority_escape_exemption_unknown_construct:" + exemption.exemption_id)
        if not re.fullmatch(r"(?:DS\d+[a-z]?|team-[a-z0-9-]+)", exemption.owner):
            errors.append(f"authority_escape_exemption_owner_invalid:{exemption.exemption_id}")
        if len(exemption.reason.strip()) < 20:
            errors.append(f"authority_escape_exemption_reason_missing:{exemption.exemption_id}")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", exemption.site_sha256):
            errors.append(f"authority_escape_exemption_hash_invalid:{exemption.exemption_id}")
        identity = _escape_identity(exemption)
        if identity in exemption_by_identity:
            errors.append(f"authority_escape_exemption_identity_duplicate:{exemption.exemption_id}")
        exemption_by_identity[identity] = exemption

    live_by_identity = {_escape_identity(site): site for site in sites if isinstance(site, Mapping)}
    required_identities: set[tuple[Any, ...]] = set()
    for identity, site in live_by_identity.items():
        construct = site.get("construct")
        is_unsafe_satisfies = construct == "satisfies" and site.get("safety") in {
            "unsafe_brand",
            "unsafe_exhaustiveness_lookalike",
            "unsafe_widening",
        }
        requires_exemption = construct != "satisfies" or is_unsafe_satisfies
        if not requires_exemption:
            continue
        required_identities.add(identity)
        if identity not in exemption_by_identity:
            errors.append(
                "authority_escape_unregistered:"
                f"{site.get('path')}:{site.get('line')}:{site.get('column')}:"
                f"{construct}:{site.get('target')}"
            )

    for identity, exemption in exemption_by_identity.items():
        if exemption.path not in path_names:
            errors.append(f"authority_escape_exemption_unknown_path:{exemption.exemption_id}")
        if identity not in live_by_identity:
            errors.append(f"authority_escape_exemption_stale:{exemption.exemption_id}")
        elif identity not in required_identities:
            errors.append(f"authority_escape_exemption_not_required:{exemption.exemption_id}")
    return sorted(set(errors))


def validate_enforcement(
    *,
    source_overrides: Mapping[str, str] | None = None,
    enforce_authority_escapes: bool | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Validate the governed DS4 bridge and declaration-level DS5 census."""
    inventory = status_checker._load_json(status_checker.INVENTORY_PATH)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    scan = _enforcement_scan(
        source_overrides,
        inventory=inventory,
        validate_override_diagnostics=source_overrides is not None,
    )
    scan["generatedOwnerReceipt"] = _generated_owner_receipt(inventory)
    errors = _override_diagnostic_errors(scan)
    should_enforce_escapes = (
        source_overrides is None if enforce_authority_escapes is None else enforce_authority_escapes
    )
    if should_enforce_escapes:
        errors.extend(
            _authority_escape_errors(
                scan,
                exemptions=(AUTHORITY_ESCAPE_EXEMPTIONS if source_overrides is None else ()),
                enforce_denominator=source_overrides is None,
            )
        )
    if source_overrides is None:
        errors.extend(status_checker.validate_inventory(inventory, debt, live_probes=True))
        disposition = disposition_checker._load_json(disposition_checker.REGISTER_PATH)
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
    probe_path = "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerCorruptionProbe.tsx"
    angle_probe_path = (
        "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerAngleCorruptionProbe.ts"
    )
    namespace_probe_path = (
        "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerNamespaceCorruptionProbe.tsx"
    )
    nocheck_probe_path = (
        "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerNocheckCorruptionProbe.tsx"
    )
    prose_probe_path = (
        "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerDirectiveProseProbe.tsx"
    )
    type_shapes_path = "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerAuthorityTypes.ts"
    type_shapes = (
        dedent(
            """
            export interface SafeShape { payload: string }
            export interface UnsafeShape { payload: unknown }
            """
        ).strip()
        + "\n"
    )
    exports = (
        dedent(
            """
        export { AuthorityBadge } from "./primitives/AuthorityBadge";
        export type { AuthorityPresentation } from "./primitives/AuthorityBadge";
        export { createOpaqueAuthorityPresentation } from "./primitives/AuthorityBadge";
        export { Button } from "./primitives/Button";
        """
        ).strip()
        + "\n"
    )

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
    if [item.get("code") for item in scan.get("overrideDiagnostics", [])] != [2322] or not any(
        error.endswith(":TS2322") for error in errors
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
    if (
        errors
        or (
            "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
            "presentation",
        )
        not in pairs
        or (
            "packages/atlas-ui/src/primitives/Button.tsx",
            "disabled",
        )
        not in pairs
        or any("packageOwnerCorruptionProbe" in str(path) for path, _ in pairs)
    ):
        escaped.append("real-atlas-declaration-census")

    inventory = status_checker._load_json(status_checker.INVENTORY_PATH)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    corrupted = copy.deepcopy(inventory)
    corrupted["sources"]["generated_client"]["canonical_sha256"] = "sha256:" + "0" * 64
    expected = (
        "inventory_source_hash_drift:" + inventory["sources"]["generated_client"]["canonical_path"]
    )
    if expected not in status_checker.validate_inventory(corrupted, debt, live_probes=False):
        escaped.append("generated-owner-content-binding")

    errors, scan = validate_enforcement(
        source_overrides={
            package_path: exports,
            type_shapes_path: type_shapes,
            probe_path: dedent(
                """
                import type { RunOperatorProjectionStateLabel } from "@polisyos/runtime-api-client";
                import * as Atlas from "@polisyos/atlas-ui";
                type BrandAlias = Readonly<Atlas.AuthorityPresentation>;
                type WideningAlias = any;
                declare const widening: unknown;
                declare const safe: { payload: string };
                const issued = Atlas.createOpaqueAuthorityPresentation("owner");
                const asserted = {} as unknown as Atlas.AuthorityPresentation;
                const anyTyped: any = issued;
                // @ts-ignore bounded corruption witness
                const ignored: Atlas.AuthorityPresentation = {};
                // @ts-expect-error bounded corruption witness
                const expected: Atlas.AuthorityPresentation = {};
                const branded = issued satisfies BrandAlias;
                const widened = issued satisfies WideningAlias;
                const queried = "owner" satisfies typeof widening;
                const imported = { payload: "owner" } satisfies
                  import("./packageOwnerAuthorityTypes").UnsafeShape;
                const safeQuery = { payload: "owner" } satisfies typeof safe;
                const safeImport = { payload: "owner" } satisfies
                  import("./packageOwnerAuthorityTypes").SafeShape;
                const generated = {
                  authority: "runtime_authority",
                  label: "owner label",
                  state: "rejected",
                } satisfies RunOperatorProjectionStateLabel;
                export const Probe = () => <Atlas.AuthorityBadge presentation={issued} />;
                void asserted; void anyTyped; void ignored; void expected;
                void branded; void widened; void generated;
                void queried; void imported; void safeQuery; void safeImport;
                """
            ).strip()
            + "\n",
        },
        enforce_authority_escapes=True,
    )
    escape_sites = scan.get("authorityEscapeSites", [])
    observed = {
        str(site.get("construct"))
        for site in escape_sites
        if isinstance(site, Mapping)
        and (
            site.get("construct") != "satisfies"
            or str(site.get("safety", "")).startswith("unsafe_")
        )
    }
    if not {
        "as_assertion",
        "explicit_any",
        "ts_ignore",
        "ts_expect_error",
        "satisfies",
    }.issubset(observed) or not any(
        error.startswith("authority_escape_unregistered:") for error in errors
    ):
        escaped.append("authority-escape-syntax")
    if any(error.startswith("invalid_source_override:") for error in errors):
        escaped.append("authority-escape-witness-diagnostics")
    if not any(
        isinstance(site, Mapping)
        and site.get("construct") == "satisfies"
        and site.get("safety") == "generated_conformance"
        for site in escape_sites
    ):
        escaped.append("authority-escape-benign-generated-conformance")
    resolved_safety = {
        str(site.get("target")): str(site.get("safety"))
        for site in escape_sites
        if isinstance(site, Mapping) and site.get("construct") == "satisfies"
    }
    if resolved_safety.get("typeof widening") != "unsafe_widening" or (
        resolved_safety.get('import("./packageOwnerAuthorityTypes").UnsafeShape')
        != "unsafe_widening"
    ):
        escaped.append("authority-escape-resolved-widening")
    if resolved_safety.get("typeof safe") != "unrelated_conformance" or (
        resolved_safety.get('import("./packageOwnerAuthorityTypes").SafeShape')
        != "unrelated_conformance"
    ):
        escaped.append("authority-escape-resolved-benign")

    errors, scan = validate_enforcement(
        source_overrides={
            package_path: exports,
            angle_probe_path: dedent(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const issued = Atlas.createOpaqueAuthorityPresentation("owner");
                const presentation = <Atlas.AuthorityPresentation>issued;
                void presentation;
                """
            ).strip()
            + "\n",
            namespace_probe_path: dedent(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                const Sink = Atlas["AuthorityBadge"];
                const forged: any = {};
                export const Probe = () => <Sink presentation={forged} />;
                """
            ).strip()
            + "\n",
            nocheck_probe_path: dedent(
                """
                // @ts-nocheck bounded corruption witness
                import * as Atlas from "@polisyos/atlas-ui";
                const presentation: Atlas.AuthorityPresentation = {};
                export const Probe = () =>
                  <Atlas.AuthorityBadge presentation={presentation} />;
                """
            ).strip()
            + "\n",
            prose_probe_path: dedent(
                """
                import * as Atlas from "@polisyos/atlas-ui";
                // Documentation says never spell `@ts-ignore` here.
                const presentation =
                  Atlas.createOpaqueAuthorityPresentation("owner");
                export const Probe = () =>
                  <Atlas.AuthorityBadge presentation={presentation} />;
                """
            ).strip()
            + "\n",
        },
        enforce_authority_escapes=True,
    )
    if any(error.startswith("invalid_source_override:") for error in errors):
        escaped.append("authority-escape-local-witness-diagnostics")
    local_sites = [
        site for site in scan.get("authorityEscapeSites", []) if isinstance(site, Mapping)
    ]
    expected_local_constructs = {
        angle_probe_path: "type_assertion",
        namespace_probe_path: "explicit_any",
        nocheck_probe_path: "ts_nocheck",
    }
    if any(
        not any(
            site.get("path") == expected_path and site.get("construct") == expected_construct
            for site in local_sites
        )
        for expected_path, expected_construct in expected_local_constructs.items()
    ) or any(site.get("path") == prose_probe_path for site in local_sites):
        escaped.append("authority-escape-local-syntax")
    authority_paths = {
        str(row.get("path"))
        for row in scan.get("authorityPathFiles", [])
        if isinstance(row, Mapping)
    }
    if namespace_probe_path not in authority_paths:
        escaped.append("authority-escape-namespace-element-import")
    if not any(error.startswith("authority_escape_unregistered:") for error in errors):
        escaped.append("authority-escape-local-rejection")

    _production_errors, production_scan = validate_enforcement(enforce_authority_escapes=False)
    first_exemption = AUTHORITY_ESCAPE_EXEMPTIONS[0]
    moved = first_exemption._replace(line=first_exemption.line + 1)
    moved_errors = _authority_escape_errors(
        production_scan,
        exemptions=(moved, *AUTHORITY_ESCAPE_EXEMPTIONS[1:]),
    )
    if not any(
        error == f"authority_escape_exemption_stale:{first_exemption.exemption_id}"
        for error in moved_errors
    ):
        escaped.append("authority-escape-exemption-binding")
    return escaped


def _summary(scan: Mapping[str, Any]) -> dict[str, Any]:
    inventory = status_checker._load_json(status_checker.INVENTORY_PATH)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    status_summary = status_checker._summary(inventory, debt)
    denominators = scan.get("sourceDenominators", {})
    return {
        "atlas_ui_production_sources": denominators.get("atlasUiProduction"),
        "authority_sink_declarations": len(scan.get("authoritySinkDeclarations", [])),
        "authority_badge_sites": len(scan.get("badgeSites", [])),
        "authority_prop_groups": len(scan.get("authorityPropCensus", [])),
        "authority_path_files": len(scan.get("authorityPathFiles", [])),
        "authority_escape_sites": len(scan.get("authorityEscapeSites", [])),
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
