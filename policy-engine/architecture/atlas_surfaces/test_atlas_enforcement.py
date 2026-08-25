"""Behavioral tests for the retained DS5 enforcement core."""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from textwrap import dedent
from typing import Any, Mapping

ATLAS_DIR = Path(__file__).resolve().parent
ENFORCEMENT_CHECKER_PATH = ATLAS_DIR / "check_atlas_enforcement.py"
FRONTEND_DISPOSITION_CHECKER_PATH = ATLAS_DIR / "check_frontend_disposition_register.py"

_SPEC = importlib.util.spec_from_file_location(
    "atlas_enforcement_checker", ENFORCEMENT_CHECKER_PATH
)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to import enforcement checker from {ENFORCEMENT_CHECKER_PATH}")
checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(checker)

_FRONTEND_DISPOSITION_SPEC = importlib.util.spec_from_file_location(
    "frontend_disposition_checker", FRONTEND_DISPOSITION_CHECKER_PATH
)
if _FRONTEND_DISPOSITION_SPEC is None or _FRONTEND_DISPOSITION_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(
        "Unable to import frontend disposition checker from "
        f"{FRONTEND_DISPOSITION_CHECKER_PATH}"
    )
frontend_disposition_checker = importlib.util.module_from_spec(_FRONTEND_DISPOSITION_SPEC)
_FRONTEND_DISPOSITION_SPEC.loader.exec_module(frontend_disposition_checker)

PACKAGE_PATH = "packages/atlas-ui/src/index.ts"
PROBE_PATH = "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerProbe.tsx"
TS_PROBE_PATH = "apps/runtime-dashboard/src/shared/lib/domain/packageOwnerProbe.ts"
TYPE_SHAPES_PATH = "apps/runtime-dashboard/src/shared/lib/domain/authorityEscapeTypes.ts"
CAPABILITIES_PATH = "apps/runtime-dashboard/src/api/hooks/useCapabilities.ts"
AUTHORITY_BADGE_PATH = "packages/atlas-ui/src/primitives/AuthorityBadge.tsx"
EVIDENCE_TYPES_PATH = "packages/atlas-ui/src/primitives/evidenceTypes.ts"
AUTHORITY_SEMANTIC_COPY_PATH = "apps/runtime-dashboard/src/shared/ui/AuthoritySemanticCopy.ts"
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

    def test_unknown_authz_decision_never_defaults_authority_surface_to_allow(
        self,
    ) -> None:
        """Bind the phased N010 default set to the real decision API imports."""
        inventory = checker.status_checker._load_json(
            checker.status_checker.INVENTORY_PATH
        )
        live_scan = checker._enforcement_scan(
            None,
            inventory=inventory,
            validate_override_diagnostics=False,
        )
        self.assertEqual([], checker._authz_default_allow_errors(live_scan))
        facts = live_scan["authzDecisionFacts"]
        self.assertEqual([], facts["defaultAllowSites"])
        self.assertEqual((), checker.C09B_DEFERRED_AUTHZ_DEFAULTS)

        workspace_path = (
            "apps/runtime-dashboard/src/app/routes/WorkspaceBoundary.tsx"
        )
        workspace_source = (
            checker.status_checker.REPO_ROOT / workspace_path
        ).read_text(
            encoding="utf-8"
        )
        safe = (
            'const workspaceAllowed =\n'
            '    authzDecision.kind === "verified" &&\n'
            "    authzDecision.isWorkspaceAllowed(workspaceKey);"
        )
        unsafe = (
            'const workspaceAllowed =\n'
            '    authzDecision.kind === "verified"\n'
            "      ? authzDecision.isWorkspaceAllowed(workspaceKey)\n"
            "      : true;"
        )
        self.assertIn(safe, workspace_source)
        unsafe_scan = checker._enforcement_scan(
            {workspace_path: workspace_source.replace(safe, unsafe, 1)},
            inventory=inventory,
            validate_override_diagnostics=True,
            include_dashboard_program_roots=True,
        )
        self.assertTrue(
            any(
                error.startswith(
                    "authz_default_allow_unclassified:"
                    f"{workspace_path}:conditional_true:"
                )
                for error in checker._authz_default_allow_errors(unsafe_scan)
            ),
            checker._authz_default_allow_errors(unsafe_scan),
        )

        lookalike_path = (
            "apps/runtime-dashboard/src/shared/lib/authzDecisionLookalike.ts"
        )
        lookalike_scan = checker._enforcement_scan(
            {
                lookalike_path: (
                    "function useAuthzDecision() { return undefined; }\n"
                    "const authz = useAuthzDecision();\n"
                    "export const allowed = authz?.can('runs.launch') ?? true;\n"
                )
            },
            inventory=inventory,
            validate_override_diagnostics=True,
            include_dashboard_program_roots=True,
        )
        self.assertFalse(
            any(
                site["path"] == lookalike_path
                for site in lookalike_scan["authzDecisionFacts"][
                    "defaultAllowSites"
                ]
            )
        )

        bounded_path = (
            "apps/runtime-dashboard/src/shared/lib/authzDecisionBoundedSyntax.ts"
        )
        bounded_scan = checker._enforcement_scan(
            {
                bounded_path: (
                    'import { useMaybeAuthz } from "@/app/authz/AuthzProvider";\n'
                    'export const inline = useMaybeAuthz()?.can("runs.launch") ?? true;\n'
                    "const direct = useMaybeAuthz();\n"
                    "const aliased = direct;\n"
                    'export const oneStepAlias = aliased?.can("runs.launch") ?? true;\n'
                    "const propertySource = useMaybeAuthz();\n"
                    "const can = propertySource?.can;\n"
                    'export const propertyAlias = can?.("runs.launch") ?? true;\n'
                    "const destructureSource = useMaybeAuthz();\n"
                    "const { isWorkspaceAllowed } = destructureSource ?? {};\n"
                    "export const destructured =\n"
                    '  isWorkspaceAllowed?.("runsDecisions") ?? true;\n'
                    "const conditional = useMaybeAuthz();\n"
                    "export const trueConsequent = !conditional\n"
                    "  ? true\n"
                    '  : conditional.can("runs.launch");\n'
                    "export const unrelatedReceiver =\n"
                    "  ({ can: () => undefined, marker: useMaybeAuthz() }).can() ?? true;\n"
                    "const safe = useMaybeAuthz();\n"
                    'export const falseDefault = safe?.can("runs.launch") ?? false;\n'
                    "export const explicitTruthTable = safe?.can(\"runs.launch\")\n"
                    "  ? true\n"
                    "  : false;\n"
                    "const indirect = () => useMaybeAuthz()?.can(\"runs.launch\");\n"
                    "export const declaredResidual = indirect() ?? true;\n"
                )
            },
            inventory=inventory,
            validate_override_diagnostics=True,
            include_dashboard_program_roots=True,
        )
        bounded_sites = [
            site
            for site in bounded_scan["authzDecisionFacts"]["defaultAllowSites"]
            if site["path"] == bounded_path
        ]
        self.assertEqual(
            {"conditional_true": 1, "nullish_true": 4},
            {
                kind: sum(site["kind"] == kind for site in bounded_sites)
                for kind in {site["kind"] for site in bounded_sites}
            },
        )
        self.assertEqual(
            checker.C09A_AUTHZ_DIRECT_SYNTAX_RESIDUAL,
            bounded_scan["authzDecisionFacts"]["residual"],
        )
        bounded_errors = checker._authz_default_allow_errors(bounded_scan)
        self.assertEqual(
            5,
            sum(
                error.startswith(
                    f"authz_default_allow_unclassified:{bounded_path}:"
                )
                for error in bounded_errors
            ),
            bounded_errors,
        )

    def test_raw_local_state_envelope_cannot_be_issued_or_written(self) -> None:
        """Execute the scoped local-state runtime witness instead of grepping it."""
        self.assertEqual([], checker._authority_local_state_runtime_errors())

    def test_query_policy_splits_wrapper_construction_from_feature_producer(self) -> None:
        """Bind C12b construction to the wrapper while retaining the feature producer."""
        self.assertEqual(  # noqa: PT009 - unittest keeps the expected identity visible.
            "apps/runtime-dashboard/src/api/governedQueryPolicy.ts",
            checker.QUERY_CACHE_POLICY_GOVERNED_CONSTRUCTION["path"],
        )
        self.assertEqual(  # noqa: PT009 - unittest keeps the expected identity visible.
            "apps/runtime-dashboard/src/features/runs/api/useDepthNCycleBoardProjection.ts",
            checker.QUERY_CACHE_POLICY_GOVERNED_PRODUCER["path"],
        )
        self.assertIsNone(  # noqa: PT009 - unittest keeps the absence explicit.
            checker.QUERY_CACHE_POLICY_GOVERNED_CONSTRUCTION["options_declaration"]
        )
        self.assertEqual(  # noqa: PT009 - unittest keeps the syntax class explicit.
            "referenced",
            checker.QUERY_CACHE_POLICY_GOVERNED_CONSTRUCTION["options_resolution"],
        )

    def test_offline_queue_type_rejects_authority_action_kind(self) -> None:
        """Keep composer-only drafts from becoming a replayable authority channel."""
        self.assertTrue(
            checker._offline_queue_errors(
                {
                    "offlineQueueFacts": {
                        "authorityActionKinds": [
                            {
                                "kind": "publication.reissue",
                                "path": "apps/runtime-dashboard/src/app/offline/composerDraftDb.ts",
                            }
                        ],
                        "composerDbImports": [],
                        "mutationStores": [],
                        "optimisticAuthorityProjections": [],
                        "productionFiles": 587,
                        "replayDeclarations": [],
                    }
                },
                enforce_denominator=True,
            )
        )
        inventory = checker.status_checker._load_json(checker.status_checker.INVENTORY_PATH)
        scan = checker._enforcement_scan(
            None,
            inventory=inventory,
            validate_override_diagnostics=False,
        )
        self.assertEqual(
            [],
            checker._offline_queue_errors(scan, enforce_denominator=True),
        )

        facts = scan["offlineQueueFacts"]
        self.assertEqual(588, facts["productionFiles"])
        self.assertEqual([], facts["authorityActionKinds"])
        self.assertEqual([], facts["mutationStores"])
        self.assertEqual([], facts["replayDeclarations"])
        self.assertEqual([], facts["optimisticAuthorityProjections"])
        self.assertEqual(
            [
                {
                    "bindings": [
                        "deleteComposerDraftRecord",
                        "loadComposerDraftRecord",
                        "saveComposerDraftRecord",
                    ],
                    "path": "apps/runtime-dashboard/src/features/composer/state/composerDraftRepository.ts",
                    "targetPath": checker.COMPOSER_DRAFT_DB_PATH,
                }
            ],
            facts["composerDbImports"],
        )

        def merge_overrides(overrides: dict[str, str]) -> dict[str, Any]:
            override_scan = checker._enforcement_scan(
                overrides,
                inventory=checker.status_checker._load_json(checker.status_checker.INVENTORY_PATH),
                validate_override_diagnostics=True,
            )
            self.assertEqual([], override_scan["overrideDiagnostics"], override_scan)
            merged = copy.deepcopy(scan)
            for table in (
                "authorityActionKinds",
                "composerDbImports",
                "mutationStores",
                "optimisticAuthorityProjections",
                "replayDeclarations",
            ):
                merged["offlineQueueFacts"][table] = [
                    row
                    for row in merged["offlineQueueFacts"][table]
                    if row["path"] not in overrides
                ] + copy.deepcopy(override_scan["offlineQueueFacts"][table])
            return merged

        composer_db_source = (
            checker.status_checker.REPO_ROOT / checker.COMPOSER_DRAFT_DB_PATH
        ).read_text(encoding="utf-8")
        db_path = "apps/runtime-dashboard/src/app/offline/db.ts"
        db_source = (checker.status_checker.REPO_ROOT / db_path).read_text(encoding="utf-8")
        replay_path = "apps/runtime-dashboard/src/app/providers/OfflineQueueProvider.tsx"
        authority_import_path = (
            "apps/runtime-dashboard/src/features/evidence/hooks/authorityQueueProbe.ts"
        )
        optimistic_projection_path = (
            "apps/runtime-dashboard/src/features/evidence/hooks/optimisticQueueProbe.ts"
        )
        corrupted_scan = merge_overrides(
            {
                checker.COMPOSER_DRAFT_DB_PATH: composer_db_source
                + (
                    "\nexport type OfflineAuthorityReplayKind = "
                    '"publication.reissue" | "reissue.approval" | "approval.publish";\n'
                ),
                db_path: db_source
                + (
                    "\nexport function reopenAuthorityMutationStore(database: { "
                    "createObjectStore: (name: string) => void }) {\n"
                    '  database.createObjectStore("authority-mutations");\n'
                    "}\n"
                ),
                replay_path: (
                    "export function OfflineQueueProvider() { return null; }\n"
                    "export async function replayQueuedAuthorityMutation() {}\n"
                ),
                authority_import_path: (
                    'import { saveComposerDraftRecord } from "@/app/offline/composerDraftDb";\n'
                    "export async function persistAuthorityDecision() {\n"
                    '  await saveComposerDraftRecord({ key: "promotion.approve" });\n'
                    "}\n"
                ),
                optimistic_projection_path: (
                    'import type { QueryClient } from "@tanstack/react-query";\n'
                    'import { applyOptimisticPromotionDecision } from "@/api/hooks/usePromotionDecision";\n'
                    "export function projectQueuedApproval(client: QueryClient) {\n"
                    '  applyOptimisticPromotionDecision(client, "promotion-1", "approved");\n'
                    "}\n"
                ),
            }
        )
        corrupted_facts = corrupted_scan["offlineQueueFacts"]
        self.assertEqual(
            ["approval.publish | publication.reissue | reissue.approval"],
            [row["kind"] for row in corrupted_facts["authorityActionKinds"]],
        )
        self.assertEqual(
            [db_path],
            [row["path"] for row in corrupted_facts["mutationStores"]],
        )
        self.assertEqual(
            [checker.COMPOSER_DRAFT_ADAPTER_PATH, authority_import_path],
            [row["path"] for row in corrupted_facts["composerDbImports"]],
        )
        self.assertEqual(
            [optimistic_projection_path],
            [row["path"] for row in corrupted_facts["optimisticAuthorityProjections"]],
        )
        self.assertEqual(
            [checker.COMPOSER_DRAFT_DB_PATH, replay_path, replay_path],
            [row["path"] for row in corrupted_facts["replayDeclarations"]],
        )
        self.assertTrue(
            checker._offline_queue_errors(
                corrupted_scan,
                enforce_denominator=True,
            )
        )

    def test_offline_queue_denominator_tracks_scanned_production_sources(self) -> None:
        """Bind the queue facts and denominator to one live TypeScript source set."""
        inventory = checker.status_checker._load_json(checker.status_checker.INVENTORY_PATH)
        live_scan = checker._enforcement_scan(
            None,
            inventory=inventory,
            validate_override_diagnostics=False,
        )
        test_path = (
            "apps/runtime-dashboard/src/shared/lib/domain/"
            "offlineQueueDenominator.test.ts"
        )
        production_path = test_path.replace(".test.ts", ".ts")
        queue_declaration = 'export type QueueActionKind = "publication.reissue";\n'
        test_source_scan = checker._enforcement_scan(
            {test_path: queue_declaration},
            inventory=inventory,
            validate_override_diagnostics=False,
            include_dashboard_program_roots=True,
        )
        locale_json_paths = (
            "apps/runtime-dashboard/src/shared/i18n/locales/en.json",
            "apps/runtime-dashboard/src/shared/i18n/locales/ru.json",
            "apps/runtime-dashboard/src/shared/i18n/locales/uk.json",
        )
        production_source_scan = checker._enforcement_scan(
            {production_path: queue_declaration},
            inventory=inventory,
            validate_override_diagnostics=False,
            include_dashboard_program_roots=True,
        )

        live_facts = live_scan["offlineQueueFacts"]
        test_source_delta = test_source_scan["offlineQueueFacts"]["productionFiles"]
        production_source_delta = production_source_scan["offlineQueueFacts"]["productionFiles"]
        self.assertEqual(588, live_facts["productionFiles"])  # noqa: PT009 - live receipt.
        self.assertEqual(591, live_facts["definitionFiles"])  # noqa: PT009 - broad receipt.
        self.assertEqual(  # noqa: PT009 - the three exclusions are source-derived.
            list(locale_json_paths), live_facts["nonTypeScriptDefinitionFiles"]
        )
        self.assertEqual(588, test_source_delta)  # noqa: PT009 - test roots are excluded.
        self.assertEqual(589, production_source_delta)  # noqa: PT009 - production is selected.
        self.assertEqual(  # noqa: PT009 - the virtual test retains the live denominator.
            checker.OFFLINE_QUEUE_PRODUCTION_SOURCE_COUNT,
            test_source_delta,
        )
        test_facts = test_source_scan["offlineQueueFacts"]
        for table in (
            "authorityActionKinds",
            "composerDbImports",
            "mutationStores",
            "optimisticAuthorityProjections",
            "replayDeclarations",
        ):
            with self.subTest(table=table):
                self.assertEqual(  # noqa: PT009 - test roots must leave each fact table unchanged.
                    live_facts[table], test_facts[table]
                )
        self.assertEqual(  # noqa: PT009 - test roots leave the queue gate green.
            [], checker._offline_queue_errors(test_source_scan, enforce_denominator=True)
        )
        self.assertEqual(  # noqa: PT009 - the selected production file emits the fact.
            [
                {
                    "kind": "publication.reissue",
                    "name": "QueueActionKind",
                    "path": production_path,
                }
            ],
            production_source_scan["offlineQueueFacts"]["authorityActionKinds"],
        )
        self.assertEqual(  # noqa: PT009 - the production source must name its drift.
            [
                "offline_queue_authority_action_kind:" + production_path,
                "offline_queue_production_source_denominator_drift",
            ],
            checker._offline_queue_errors(production_source_scan, enforce_denominator=True),
        )

    def test_c13a_terminal_dispositions_have_live_census_and_composer_rebind(self) -> None:
        """Require C13a terminal rows to carry a fresh zero-consumer receipt."""
        data = json.loads(
            frontend_disposition_checker._refresh_supplemental_findings_text(
                frontend_disposition_checker.REGISTER_PATH.read_text(
                    encoding="utf-8"
                )
            )
        )
        unit_ids = {
            "status-offline-queue-item",
            "status-inline-queued-promotion",
            "offline-queue-promotion-decision",
        }
        rows = {
            row["unit_id"]: row
            for row in data["entries"]
            if row["unit_id"] in unit_ids
        }
        self.assertEqual(unit_ids, set(rows))
        self.assertTrue(
            all(
                row["disposition"] == "deleted"
                and row["strangle_status"] == "strangled"
                and row["reference_census_id"] == "census-c13a-authority-replay-delete"
                for row in rows.values()
            ),
            rows,
        )
        census = next(
            row
            for row in data["reference_censuses"]
            if row["census_id"] == "census-c13a-authority-replay-delete"
        )
        self.assertEqual("zero_consumers", census["result"])
        self.assertEqual(unit_ids, set(census["covers_unit_ids"]))
        for probe in census["probes"]:
            self.assertEqual([], frontend_disposition_checker._recompute_probe(probe))

        self.assertEqual(
            [],
            frontend_disposition_checker.validate_register(
                data,
                report_parity=False,
            ),
        )

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

    def test_capability_discovery_direct_syntax_reports_enclosure_residual(self) -> None:
        """Make the bounded scanner's non-flow residual explicit."""
        summary = checker._summary({})
        self.assertEqual(
            "indirect enclosure identity, including nested same-name functions, is outside "
            "the direct-syntax/construction-site rule",
            summary["capability_discovery_residual"],
        )
        capability_source = (checker.status_checker.REPO_ROOT / CAPABILITIES_PATH).read_text(
            encoding="utf-8"
        ).replace(
            "  return discoverCapabilities(useCapabilities());",
            "  function discoverCapabilities(\n"
            "    query: UseQueryResult<CapabilityManifestResponse>,\n"
            "  ): CapabilityDiscovery {\n"
            "    if (!query.data) {\n"
            "      return issueCapabilityDiscovery({ reason: \"missing_data\", state: \"unavailable\" });\n"
            "    }\n"
            "    return issueCapabilityDiscovery({ manifest: query.data, state: \"available\" });\n"
            "  }\n"
            "  return discoverCapabilities(useCapabilities());",
            1,
        )
        _errors, scan = self._validate(
            ATLAS_EXPORTS,
            ts_source("export {}"),
            extra_sources={CAPABILITIES_PATH: capability_source},
        )
        self.assertEqual([], scan["overrideDiagnostics"])
        self.assertEqual([], checker._capability_discovery_errors(scan))

    def test_capability_discovery_reviewer_syntax_witnesses_fail(self) -> None:
        """Reject direct owner-query syntax, leaving indirect enclosure as a residual."""
        capability_source = (checker.status_checker.REPO_ROOT / CAPABILITIES_PATH).read_text(
            encoding="utf-8"
        )
        witnesses = {
            "local_query_result_lookalike": capability_source.replace(
                "  type UseQueryResult,\n", "", 1
            ).replace(
                "function discoverCapabilities(",
                "type UseQueryResult<T> = {\n"
                "  data?: T;\n  isError: boolean;\n  isLoading: boolean;\n  isPaused: boolean;\n"
                "};\n\nfunction discoverCapabilities(",
                1,
            ),
            "local_manifest_lookalike": capability_source.replace(
                "function discoverCapabilities(",
                "namespace Local {\n"
                "  export type CapabilityManifestResponse =\n"
                "    components[\"schemas\"][\"CapabilityManifestResponse\"] & {};\n"
                "}\n\nfunction discoverCapabilities(",
                1,
            ).replace(
                "query: UseQueryResult<CapabilityManifestResponse>,",
                "query: UseQueryResult<Local.CapabilityManifestResponse>,",
                1,
            ),
            "local_parameter": capability_source.replace(
                "export function useCapabilityDiscovery(): CapabilityDiscovery {",
                "function issueLocalManifest(\n  local: CapabilityManifestResponse,\n): CapabilityDiscovery {\n"
                "  return issueCapabilityDiscovery({ manifest: local, state: \"available\" });\n}\n\n"
                "export function useCapabilityDiscovery(): CapabilityDiscovery {",
                1,
            ),
            "helper_wrapped_query": capability_source.replace(
                "function discoverCapabilities(",
                "function wrapManifest(manifest: CapabilityManifestResponse): CapabilityManifestResponse {\n"
                "  return manifest;\n}\n\nfunction discoverCapabilities(",
                1,
            ).replace(
                'return issueCapabilityDiscovery({ manifest: query.data, state: "available" });',
                "return issueCapabilityDiscovery({\n  manifest: wrapManifest(query.data),\n  state: \"available\",\n});",
                1,
            ),
            "loading_available": capability_source.replace(
                "if (query.isLoading) {",
                "if (Boolean(query.isLoading) && query.data) {\n"
                '    return issueCapabilityDiscovery({ manifest: query.data, state: "available" });\n'
                "  }\n  if (query.isLoading) {",
                1,
            ),
            "wrapped_query_data": capability_source.replace(
                'return issueCapabilityDiscovery({ manifest: query.data, state: "available" });',
                "return issueCapabilityDiscovery({\n"
                "  manifest: (query.data! as CapabilityManifestResponse),\n"
                '  state: "available",\n});',
                1,
            ),
        }
        for label, source in witnesses.items():
            with self.subTest(label=label):
                _errors, scan = self._validate(
                    ATLAS_EXPORTS,
                    ts_source("export {}"),
                    extra_sources={CAPABILITIES_PATH: source},
                )
                self.assertEqual([], scan["overrideDiagnostics"])
                self.assertTrue(
                    any(
                        "available_manifest_invalid" in error
                        for error in checker._capability_discovery_errors(scan)
                    ),
                    scan,
                )

        valid_packet = {
            "capabilityDiscoveryFacts": {
                "productionFiles": 588,
                "issuerCalls": [
                    {
                        "path": checker.CAPABILITY_DISCOVERY_OWNER_PATH,
                        "line": line,
                        "argumentKind": "object_literal",
                        "state": "unavailable",
                        "reason": "loading",
                        "manifest": None,
                    }
                    for line in range(1, 6)
                ],
                "featureLiterals": [],
            }
        }
        self.assertEqual(
            [],
            checker._capability_discovery_errors(valid_packet, enforce_denominator=True),
        )

    def test_authored_capability_discovery_construction_fails(self) -> None:
        """Reject direct issuer/literal syntax while retaining bounded controls."""
        capability_source = (checker.status_checker.REPO_ROOT / CAPABILITIES_PATH).read_text(
            encoding="utf-8"
        ).replace("function issueCapabilityDiscovery(", "export function issueCapabilityDiscovery(")
        external_issuer = ts_source(
            """
            import { issueCapabilityDiscovery } from "@/api/hooks/useCapabilities";
            export const discovery = issueCapabilityDiscovery({
              manifest: { features: [] }, state: "available",
            });
            """
        )
        _errors, scan = self._validate(
            ATLAS_EXPORTS,
            external_issuer,
            extra_sources={CAPABILITIES_PATH: capability_source},
        )
        self.assertTrue(  # noqa: PT009 - unittest reports the corrupt source payload.
            any(
                error.startswith("capability_discovery_")
                for error in checker._capability_discovery_errors(scan)
            ),
            scan,
        )

        feature_probe = ts_source(
            """
            import type { components as Components } from "@/api/types";
            import type * as Api from "@/api/types";
            type FeatureAlias = Components["schemas"]["CapabilityFeatureInfo"];
            const fromAlias: FeatureAlias = {
              stage: "active", label: "Alias", key: "alias", enabled: true,
              category: "test", description: "alias literal",
            };
            const fromNamespace: Api.components["schemas"]["CapabilityFeatureInfo"] = {
              key: "namespace", description: "namespace literal", category: "test",
              enabled: false, label: "Namespace", stage: "planned",
            };
            const featureArray: Components["schemas"]["CapabilityManifestResponse"]["features"] = [{
              description: "inline feature", category: "test", stage: "deferred",
              enabled: false, key: "inline", label: "Inline",
            }];
            void fromAlias; void fromNamespace; void featureArray;
            """
        )
        _errors, scan = self._validate(ATLAS_EXPORTS, feature_probe)
        feature_errors = checker._capability_discovery_errors(scan)
        self.assertEqual(3, len(scan["capabilityDiscoveryFacts"]["featureLiterals"]))
        self.assertEqual(3, len(feature_errors), feature_errors)
        self.assertTrue(
            all(
                error.startswith("capability_discovery_feature_literal_authored:")
                for error in feature_errors
            ),
            feature_errors,
        )

        loading_enabled = capability_source.replace(
            "if (query.isLoading) {",
            "if (Boolean(query.isLoading) && query.data) {\n"
            '    return issueCapabilityDiscovery({ manifest: query.data, state: "available" });\n'
            "  }\n  if (query.isLoading) {",
            1,
        )
        _errors, scan = self._validate(
            ATLAS_EXPORTS,
            ts_source("export {}"),
            extra_sources={CAPABILITIES_PATH: loading_enabled},
        )
        self.assertTrue(
            any(
                "available_manifest_invalid" in error
                for error in checker._capability_discovery_errors(scan)
            ),
            scan,
        )

        benign_probe = ts_source(
            """
            import type { CapabilityDiscovery } from "@/api/hooks/useCapabilities";
            declare const runtimeManifest: { features?: unknown[] };
            const fixedChrome = Array.from({ length: 43 }, (_, index) => ({
              key: `chrome-${index}`, label: "Fixed", enabled: true,
            }));
            const localLookalike = { state: "available", manifest: { features: [] } };
            const brandedConsumer: CapabilityDiscovery = localLookalike;
            void fixedChrome; void runtimeManifest; void brandedConsumer;
            """
        )
        errors, scan = self._validate(ATLAS_EXPORTS, benign_probe)
        self.assertEqual([], checker._capability_discovery_errors(scan))
        self.assertEqual([2322], [item["code"] for item in scan["overrideDiagnostics"]])
        self.assertTrue(any(error.endswith(":TS2322") for error in errors), errors)

        valid_packet = {
            "capabilityDiscoveryFacts": {
                "productionFiles": 1,
                "issuerCalls": [],
                "featureLiterals": [],
            }
        }
        malformed_packets = (
            {},
            {"capabilityDiscoveryFacts": {}},
            {"capabilityDiscoveryFacts": {**valid_packet["capabilityDiscoveryFacts"], "productionFiles": 0}},
            {"capabilityDiscoveryFacts": {**valid_packet["capabilityDiscoveryFacts"], "issuerCalls": {}}},
            {"capabilityDiscoveryFacts": {**valid_packet["capabilityDiscoveryFacts"], "featureLiterals": {}}},
        )
        self.assertEqual([], checker._capability_discovery_errors(valid_packet))
        for packet in malformed_packets:
            with self.subTest(packet=packet):
                self.assertTrue(checker._capability_discovery_errors(packet))

    def test_ds10_python_manifest_strangle_resolves_import_and_module_aliases(self) -> None:
        """Reject direct feature constructors only when they feed manifest features."""
        direct_path = "src/polisyos/runtime/http/services/control/direct_probe.py"
        module_path = "src/polisyos/runtime/http/services/control/module_probe.py"
        unrelated_path = "src/polisyos/runtime/http/services/control/unrelated_probe.py"
        contributors = checker.control_capability_manifest_contributors(
            {
                direct_path: dedent(
                    """
                    from polisyos.core.contracts.control import (
                        CapabilityFeatureInfo as Feature,
                        CapabilityManifestResponse as Manifest,
                    )
                    def build(meta):
                        projected = [Feature(key="generated", label="Generated",
                                             description="probe", category="probe")]
                        rows = tuple(projected)
                        return Manifest(meta=meta, features=rows)
                    """
                ),
                module_path: dedent(
                    """
                    import polisyos.core.contracts.control
                    def build(meta):
                        rows = []
                        rows.append(polisyos.core.contracts.control.CapabilityFeatureInfo(
                            key="generated", label="Generated",
                            description="probe", category="probe",
                        ))
                        return polisyos.core.contracts.control.CapabilityManifestResponse(
                            meta=meta, features=rows,
                        )
                    """
                ),
                unrelated_path: dedent(
                    """
                    from polisyos.core.contracts.control import CapabilityFeatureInfo
                    diagnostic = CapabilityFeatureInfo(
                        key="generated", label="Generated",
                        description="not returned in a manifest", category="probe",
                    )
                    """
                ),
            }
        )

        self.assertEqual(2, len(contributors))  # noqa: PT009
        self.assertTrue(  # noqa: PT009
            any(row.startswith(f"{direct_path}:") for row in contributors)
        )
        self.assertTrue(  # noqa: PT009
            any(row.startswith(f"{module_path}:") for row in contributors)
        )
        self.assertFalse(  # noqa: PT009
            any(row.startswith(f"{unrelated_path}:") for row in contributors)
        )

    def test_ds10_generic_render_boundary_rejects_indirect_and_sibling_literals(self) -> None:
        """Reject authored rows/branches through an imported sibling while accepting chrome."""
        generated_ref = "".join(("capability", "-", "boundary", "-", "probe"))
        errors = checker.check_capability_discovery_result_boundary(
            {
                (
                    "apps/runtime-dashboard/src/features/evidence/components/"
                    "CapabilityDiscoveryPanel.tsx"
                ): (
                    'import { renderRows } from "./CapabilityDiscoveryRows";\n'
                    "export const panel = renderRows;\n"
                ),
                (
                    "apps/runtime-dashboard/src/features/evidence/components/"
                    "CapabilityDiscoveryRows.tsx"
                ): (
                    f'const selected = "{generated_ref}";\n'
                    'const rows = [{ capability_ref: selected, resource_kind: "dataset" }];\n'
                    "export function renderRows(result: {\n"
                    "  capability_ref: string; adapter_id: string;\n"
                    "}) {\n"
                    "  switch (result.adapter_id) { case selected: return rows; }\n"
                    "  return result.capability_ref === selected ? rows : [];\n"
                    "}\n"
                ),
                "apps/runtime-dashboard/src/app/surfaces/workspaceConfig.ts": (
                    "type WorkspaceConfig = { route: string; tab: string };\n"
                    "export const workspace: WorkspaceConfig = "
                    '{ route: "runs", tab: "overview" };\n'
                ),
            }
        )

        self.assertTrue(errors)  # noqa: PT009
        self.assertTrue(  # noqa: PT009
            all("CapabilityDiscoveryRows.tsx" in error for error in errors)
        )
        self.assertFalse(  # noqa: PT009
            any("workspaceConfig" in error for error in errors)
        )

    def test_ds10_generic_render_boundary_accepts_data_driven_mapping(self) -> None:
        """Keep generic result mapping green when it carries no authored row or kind switch."""
        errors = checker.check_capability_discovery_result_boundary(
            {
                (
                    "apps/runtime-dashboard/src/features/evidence/components/"
                    "CapabilityDiscoveryPanel.tsx"
                ): (
                    "export function Panel({ results }: { results: readonly unknown[] }) {\n"
                    "  return results.map((result) => JSON.stringify(result));\n"
                    "}\n"
                )
            }
        )

        self.assertEqual([], errors)  # noqa: PT009

    def test_ds10_validate_enforcement_runs_both_checks_on_derived_sources(self) -> None:
        """Bind both generic checks to the live validation entry point."""
        python_path = "src/polisyos/runtime/http/services/control/generated_probe.py"
        render_dir = "apps/runtime-dashboard/src/features/evidence/components"
        render_path = f"{render_dir}/CapabilityDiscoveryPanel.tsx"
        errors, scan = checker.validate_enforcement(
            source_overrides={
                python_path: dedent(
                    """
                    from polisyos.core.contracts.control import (
                        CapabilityFeatureInfo as Feature,
                        CapabilityManifestResponse as Manifest,
                    )
                    def build(meta):
                        rows = [Feature(key="generated", label="Generated",
                                        description="probe", category="probe")]
                        return Manifest(meta=meta, features=rows)
                    """
                ),
                render_path: (
                    'const selected = "capability-boundary-probe";\n'
                    'export const rows = [{ capability_ref: selected, resource_kind: "method" }];\n'
                ),
            },
            enforce_authority_escapes=False,
        )

        self.assertEqual(1, len(scan["capabilityManifestContributors"]))  # noqa: PT009
        self.assertTrue(scan["capabilityDiscoveryRenderErrors"])  # noqa: PT009
        self.assertTrue(  # noqa: PT009
            any(error.startswith("authored_capability_manifest_feature:") for error in errors)
        )
        self.assertTrue(  # noqa: PT009
            any(error.startswith("hardcoded_discovery_result:") for error in errors)
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

    def test_persistence_construction_census_is_source_complete_and_bounded(self) -> None:
        """Bind direct constructions while refusing an owner-instance flow claim."""
        inventory = checker.status_checker._load_json(checker.status_checker.INVENTORY_PATH)
        register = frontend_disposition_checker._load_json(
            frontend_disposition_checker.REGISTER_PATH
        )
        live_scan = checker._enforcement_scan(
            None,
            inventory=inventory,
            validate_override_diagnostics=False,
        )
        facts = live_scan["persistenceConstructionFacts"]
        self.assertEqual(574, facts["productionSourceCount"])
        self.assertEqual(36, len(facts["sites"]))
        self.assertEqual(15, len({row["path"] for row in facts["sites"]}))
        self.assertEqual(
            {"indexed_db": 5, "web_storage": 26, "zustand": 5},
            facts["apiCounts"],
        )
        self.assertIn("indirect storage value-flow remains not_established", facts["residual"])
        census = register["storage_construction_census"]
        self.assertEqual("recomputed", census["direct_construction_provenance"])
        self.assertEqual(
            "institutionally_supplied", census["semantic_class_provenance"]
        )
        self.assertEqual("not_established", census["authority_flow_provenance"])
        self.assertEqual("absent/unallocated", census["authority_flow_capability_status"])
        self.assertIn("provider()", census["authority_flow_falsifier"])
        self.assertIn("interprocedural", census["authority_flow_required_capability"])
        self.assertTrue(
            all("authorityBinding" not in row for row in facts["sites"]), facts["sites"]
        )
        self.assertTrue(
            all("classification" not in row for row in facts["sites"]), facts["sites"]
        )
        self.assertTrue(
            all("authority_binding" not in row for row in census["sites"]),
            census["sites"],
        )
        factory_ids = {
            factory_call["factorySiteId"]
            for factory_call in facts["authorityFactoryCalls"]
        }
        self.assertEqual(
            9,
            len(factory_ids),
        )
        self.assertEqual(
            {row["siteId"] for row in facts["sites"]},
            {
                row["site_id"]
                for row in register["storage_construction_census"]["sites"]
            },
        )
        self.assertEqual(
            [], checker._persistence_construction_errors(live_scan, register=register)
        )
        first_site = register["storage_construction_census"]["sites"][0]
        for field, value, expected_prefix in (
            ("operation", "clear", "persistence_operation_drift:"),
            (
                "resolved_api_declaration",
                "typescript/lib/lib.dom.d.ts::Storage.clear",
                "persistence_resolved_declaration_drift:",
            ),
            (
                "site_fingerprint",
                "sha256:" + "0" * 64,
                "persistence_site_fingerprint_drift:",
            ),
        ):
            with self.subTest(governed_field=field):
                mutation = copy.deepcopy(register)
                row = next(
                    item
                    for item in mutation["storage_construction_census"]["sites"]
                    if item["site_id"] == first_site["site_id"]
                )
                row[field] = value
                mutation_errors = checker._persistence_construction_errors(
                    live_scan, register=mutation
                )
                self.assertTrue(
                    any(error.startswith(expected_prefix) for error in mutation_errors),
                    mutation_errors,
                )

        factory_mutation = copy.deepcopy(register)
        factory_mutation["storage_construction_census"][
            "authority_factory_receipts"
        ][0]["site_fingerprint"] = "sha256:" + "0" * 64
        self.assertTrue(
            any(
                error.startswith("persistence_authority_factory_drift:")
                for error in checker._persistence_construction_errors(
                    live_scan, register=factory_mutation
                )
            )
        )

        def override_scan(path: str, source: str) -> dict[str, Any]:
            scan = checker._enforcement_scan(
                {path: ts_source(source)},
                inventory=inventory,
                validate_override_diagnostics=True,
                include_dashboard_program_roots=True,
            )
            self.assertEqual([], scan["overrideDiagnostics"], scan)
            return scan

        direct_path = "apps/runtime-dashboard/src/shared/lib/domain/storageCensusProbe.ts"
        direct_scan = override_scan(
            direct_path,
            """
            export function writeRawEnvelope(payload: unknown) {
              const envelope = { codec: "raw", expiresAt: 1, payload, scope: "tenant" };
              window.localStorage.setItem("storage-census-probe", JSON.stringify(envelope));
            }
            """,
        )
        self.assertEqual(
            [direct_path],
            [
                row["path"]
                for row in direct_scan["persistenceConstructionFacts"]["sites"]
                if row["path"] == direct_path
            ],
        )
        direct_rows = [
            row
            for row in direct_scan["persistenceConstructionFacts"]["sites"]
            if row["path"] == direct_path
        ]
        direct_errors = checker._persistence_construction_errors(
            direct_scan, register=register
        )
        self.assertTrue(
            all(
                f"persistence_unregistered_site:{row['siteId']}" in direct_errors
                for row in direct_rows
            ),
            direct_errors,
        )

        lookalike_path = "apps/runtime-dashboard/src/shared/lib/domain/storageLookalikeProbe.ts"
        lookalike_scan = override_scan(
            lookalike_path,
            """
            export function writeFakeStorage() {
              const localStorage = { setItem(_key: string, _value: string) {} };
              localStorage.setItem("candidate", "not-storage");
            }
            """,
        )
        self.assertEqual(
            [],
            [
                row
                for row in lookalike_scan["persistenceConstructionFacts"]["sites"]
                if row["path"] == lookalike_path
            ],
        )
        set_control_path = (
            "apps/runtime-dashboard/src/shared/lib/domain/storageSetControl.ts"
        )
        set_control_scan = override_scan(
            set_control_path,
            """
            class FakeSet { add(_value: string) {} }
            const fake = new FakeSet();
            const real = new Set<string>();
            fake.add("candidate");
            real.add("candidate");
            """,
        )
        self.assertEqual(
            [],
            [
                row
                for row in set_control_scan["persistenceConstructionFacts"]["sites"]
                if row["path"] == set_control_path
            ],
        )

        alias_path = "apps/runtime-dashboard/src/shared/lib/domain/storageAliasProbe.ts"
        alias_scan = override_scan(
            alias_path,
            """
            const storage = window.localStorage;
            const { getItem } = storage;
            const setItem = storage.setItem.bind(storage);
            getItem("candidate");
            setItem("candidate", "value");
            Storage.prototype.removeItem.call(storage, "candidate");
            """,
        )
        alias_rows = [
            row
            for row in alias_scan["persistenceConstructionFacts"]["sites"]
            if row["path"] == alias_path
        ]
        self.assertEqual(
            ["acquire", "getItem", "removeItem", "setItem"],
            sorted(row["operation"] for row in alias_rows),
        )

        authority_path = "apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts"
        authority_source = (
            checker.status_checker.REPO_ROOT / authority_path
        ).read_text(encoding="utf-8")
        authority_scan = checker._enforcement_scan(
            {
                authority_path: authority_source
                + '\nwindow.localStorage.setItem("raw-authority", "{}");\n'
            },
            inventory=inventory,
            validate_override_diagnostics=False,
            include_dashboard_program_roots=True,
        )
        authority_live_ids = {
            row["siteId"]
            for row in live_scan["persistenceConstructionFacts"]["sites"]
            if row["path"] == authority_path
        }
        raw_authority_rows = [
            row
            for row in authority_scan["persistenceConstructionFacts"]["sites"]
            if row["path"] == authority_path
            and row["siteId"] not in authority_live_ids
        ]
        self.assertEqual(1, len(raw_authority_rows))
        raw_authority_errors = checker._persistence_construction_errors(
            authority_scan, register=register
        )
        self.assertIn(
            f"persistence_unregistered_site:{raw_authority_rows[0]['siteId']}",
            raw_authority_errors,
        )

        for label, source, operations in (
            (
                "provider-borrow",
                """
                function provider(): Storage { return window.localStorage; }
                export function write(value: string) {
                  const storage = provider();
                  storage.setItem("candidate", value);
                }
                """,
                {"acquire", "setItem"},
            ),
            (
                "raw-acquire",
                """
                export function write(storage: Storage, value: string) {
                  const raw = window.localStorage;
                  storage.setItem("candidate", value);
                  void raw;
                }
                """,
                {"acquire", "setItem"},
            ),
            (
                "stale-assignment",
                """
                export function write(storage: Storage, value: string) {
                  let key = "owner-derived";
                  key = "raw";
                  storage.setItem(key, value);
                }
                """,
                {"setItem"},
            ),
        ):
            with self.subTest(declared_residual=label):
                limitation_path = (
                    "apps/runtime-dashboard/src/shared/lib/domain/"
                    f"storageFlowLimitation{label.replace('-', '')}.ts"
                )
                limitation_scan = override_scan(limitation_path, source)
                limitation_rows = [
                    row
                    for row in limitation_scan["persistenceConstructionFacts"]["sites"]
                    if row["path"] == limitation_path
                ]
                self.assertEqual(
                    operations,
                    {row["operation"] for row in limitation_rows},
                )
                self.assertTrue(
                    all("authorityBinding" not in row for row in limitation_rows),
                    limitation_rows,
                )
                limitation_errors = checker._persistence_construction_errors(
                    limitation_scan, register=register
                )
                self.assertTrue(
                    all(
                        f"persistence_unregistered_site:{row['siteId']}"
                        in limitation_errors
                        for row in limitation_rows
                    ),
                    limitation_errors,
                )

        review_path = (
            "apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts"
        )
        review_scan = override_scan(
            review_path,
            """
            export function readStoredReviewAttention(runId: string) {
              return window.localStorage.getItem(`polisyos:atlas:review-attention:${runId}`);
            }
            export function writeStoredReviewAttention(runId: string, value: string) {
              window.localStorage.setItem(`polisyos:atlas:review-attention:${runId}`, value);
            }
            """,
        )
        self.assertEqual(
            2,
            len(
                [
                    row
                    for row in review_scan["persistenceConstructionFacts"]["sites"]
                    if row["path"] == review_path
                ]
            ),
        )
        review_rows = [
            row
            for row in review_scan["persistenceConstructionFacts"]["sites"]
            if row["path"] == review_path
        ]
        review_errors = checker._persistence_construction_errors(
            review_scan, register=register
        )
        self.assertTrue(
            all(
                f"persistence_unregistered_site:{row['siteId']}" in review_errors
                for row in review_rows
            ),
            review_errors,
        )

        feature_path = "apps/runtime-dashboard/src/shared/lib/featureFlags.ts"
        feature_source = (checker.status_checker.REPO_ROOT / feature_path).read_text(
            encoding="utf-8"
        )
        moved_scan = checker._enforcement_scan(
            {feature_path: "\n" + feature_source},
            inventory=inventory,
            validate_override_diagnostics=False,
            include_dashboard_program_roots=True,
        )
        moved_errors = checker._persistence_construction_errors(
            moved_scan, register=register
        )
        self.assertTrue(
            any(error.startswith("persistence_source_fingerprint_drift:") for error in moved_errors),
            moved_errors,
        )

        benign_path = "apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts"
        registered_benign = [
            row
            for row in register["storage_construction_census"]["sites"]
            if row["path"] == benign_path
        ]
        self.assertEqual(6, len(registered_benign))
        self.assertEqual(
            {"interaction_benign"},
            {row["classification"] for row in registered_benign},
        )
        for row in registered_benign:
            self.assertNotIn("owner_slice", row)
            self.assertNotIn("capability_states", row)
            self.assertNotIn("closure_signal", row)

    def test_query_construction_and_producer_censuses_are_source_complete(self) -> None:
        """Reject source construction drift rather than inferring option-value flow."""
        errors, scan = checker.validate_enforcement(enforce_authority_escapes=False)
        self.assertEqual([], errors)
        self.assertEqual(
            [],
            checker._query_cache_policy_errors(scan, enforce_denominator=True),
        )
        facts = scan["queryCachePolicyFacts"]
        self.assertEqual(43, len(facts["queryKeyOwners"]))
        self.assertEqual(66, len(facts["constructions"]))
        self.assertEqual(42, len(facts["producers"]))

        target_rows = [
            row
            for row in facts["constructions"]
            if row["path"] == checker.QUERY_CACHE_POLICY_TARGET_PATH
        ]
        self.assertEqual(1, len(target_rows))
        non_target_row = next(
            row
            for row in facts["constructions"]
            if row["path"] != checker.QUERY_CACHE_POLICY_TARGET_PATH
        )
        target_identity_corruptions = {
            "duplicate_target_path": lambda value: value["queryCachePolicyFacts"][
                "constructions"
            ].__setitem__(
                facts["constructions"].index(non_target_row),
                {
                    **copy.deepcopy(non_target_row),
                    "path": checker.QUERY_CACHE_POLICY_TARGET_PATH,
                },
            ),
            "missing_target_identity": lambda value: value["queryCachePolicyFacts"][
                "constructions"
            ].__setitem__(
                facts["constructions"].index(target_rows[0]),
                {
                    **copy.deepcopy(target_rows[0]),
                    "path": non_target_row["path"],
                },
            ),
            "wrong_target_declaration": lambda value: value["queryCachePolicyFacts"][
                "constructions"
            ].__setitem__(
                facts["constructions"].index(target_rows[0]),
                {
                    **copy.deepcopy(target_rows[0]),
                    "optionsDeclaration": {
                        "name": "wrongOptionsDeclaration",
                        "path": "apps/runtime-dashboard/src/api/governedQueryPolicy.ts",
                        "line": 1,
                    },
                },
            ),
            "wrong_target_declaration_path": lambda value: value["queryCachePolicyFacts"][
                "constructions"
            ].__setitem__(
                facts["constructions"].index(target_rows[0]),
                {
                    **copy.deepcopy(target_rows[0]),
                    "optionsDeclaration": {
                        "name": "options",
                        "path": "apps/runtime-dashboard/src/api/hooks/useHealth.ts",
                        "line": 1,
                    },
                },
            ),
        }
        for label, corrupt in target_identity_corruptions.items():
            with self.subTest(label=label):
                mutated_scan = copy.deepcopy(scan)
                corrupt(mutated_scan)
                self.assertTrue(
                    checker._query_cache_policy_errors(
                        mutated_scan,
                        enforce_denominator=True,
                        registry=checker._query_cache_policy_register_from_scan(mutated_scan),
                    )
                )

        target_producer_rows = [
            row
            for row in facts["producers"]
            if row["path"] == checker.QUERY_CACHE_POLICY_GOVERNED_PRODUCER["path"]
        ]
        self.assertEqual(1, len(target_producer_rows))
        non_target_producer = next(
            row
            for row in facts["producers"]
            if row["path"] != checker.QUERY_CACHE_POLICY_GOVERNED_PRODUCER["path"]
        )
        target_producer_identity_corruptions = {
            "duplicate_target_producer_path": lambda value: value[
                "queryCachePolicyFacts"
            ]["producers"].__setitem__(
                facts["producers"].index(non_target_producer),
                {
                    **copy.deepcopy(non_target_producer),
                    "path": checker.QUERY_CACHE_POLICY_GOVERNED_PRODUCER["path"],
                },
            ),
            "missing_target_producer_identity": lambda value: value[
                "queryCachePolicyFacts"
            ]["producers"].__setitem__(
                facts["producers"].index(target_producer_rows[0]),
                {
                    **copy.deepcopy(target_producer_rows[0]),
                    "path": non_target_producer["path"],
                },
            ),
            "wrong_target_producer_declaration": lambda value: value[
                "queryCachePolicyFacts"
            ]["producers"].__setitem__(
                facts["producers"].index(target_producer_rows[0]),
                {
                    **copy.deepcopy(target_producer_rows[0]),
                    "optionsDeclaration": {
                        **target_producer_rows[0]["optionsDeclaration"],
                        "name": "wrongOptionsDeclaration",
                    },
                },
            ),
        }
        for label, corrupt in target_producer_identity_corruptions.items():
            with self.subTest(label=label):
                mutated_scan = copy.deepcopy(scan)
                corrupt(mutated_scan)
                self.assertTrue(
                    checker._query_cache_policy_errors(
                        mutated_scan,
                        enforce_denominator=True,
                        registry=checker._query_cache_policy_register_from_scan(mutated_scan),
                    )
                )

        target_source = (
            checker.status_checker.REPO_ROOT / checker.QUERY_CACHE_POLICY_TARGET_PATH
        ).read_text(encoding="utf-8")

        def merge_override(override_path: str, override_source: str) -> dict[str, Any]:
            override_scan = checker._enforcement_scan(
                {override_path: override_source},
                inventory=checker.status_checker._load_json(checker.status_checker.INVENTORY_PATH),
                validate_override_diagnostics=True,
            )
            self.assertEqual(  # noqa: PT009 - unittest keeps the diagnostic payload on failure.
                [], override_scan["overrideDiagnostics"], override_scan
            )
            override_facts = override_scan["queryCachePolicyFacts"]
            relevant_override_rows = [
                row
                for table in ("constructions", "producers")
                for row in override_facts[table]
                if row["path"] == override_path
            ]
            self.assertTrue(relevant_override_rows)  # noqa: PT009 - unittest keeps diagnostics.
            merged = copy.deepcopy(scan)
            merged_facts = merged["queryCachePolicyFacts"]
            for table in ("constructions", "producers"):
                override_rows = [
                    row for row in override_facts[table] if row["path"] == override_path
                ]
                merged_facts[table] = [
                    row
                    for row in merged_facts[table]
                    if row["path"] != override_path
                ] + copy.deepcopy(override_rows)
            return merged

        def merge_target_override(override_source: str) -> dict[str, Any]:
            return merge_override(checker.QUERY_CACHE_POLICY_TARGET_PATH, override_source)

        newline_scan = merge_target_override(
            target_source.replace(
                "export function useGovernedQuery<",
                "\nexport function useGovernedQuery<",
                1,
            )
        )
        newline_register = checker._query_cache_policy_register_from_scan(newline_scan)
        self.assertEqual(
            [],
            checker._query_cache_policy_errors(
                newline_scan,
                enforce_denominator=True,
                registry=newline_register,
            ),
        )
        self.assertEqual(
            {"governed_wrapper": 1, "legacy_direct_debt": 65},
            {
                label: sum(
                    row["classification"] == label
                    for row in newline_register["constructions"]
                )
                for label in ("governed_wrapper", "legacy_direct_debt")
            },
        )

        added_call_scan = merge_target_override(
            target_source.replace(
                "  const query = useQuery(options);",
                "  const extra = useQuery(options);\n"
                "  const query = useQuery(options);\n"
                "  void extra;",
                1,
            )
        )
        self.assertEqual(67, len(added_call_scan["queryCachePolicyFacts"]["constructions"]))
        self.assertTrue(
            any(
                row["path"] == checker.QUERY_CACHE_POLICY_TARGET_PATH
                and row["optionsResolution"] == "referenced"
                for row in added_call_scan["queryCachePolicyFacts"]["constructions"]
            )
        )
        self.assertTrue(checker._query_cache_policy_errors(added_call_scan, enforce_denominator=True))

        target_factory_source_corruptions = {
            "moved": target_source.replace(
                "useQuery(options)",
                "useQuery({ queryKey: options.queryKey, queryFn: options.queryFn })",
                1,
            ),
            "duplicate": target_source.replace(
                "  const query = useQuery(options);",
                "  const duplicate = useQuery(options);\n"
                "  const query = useQuery(options);\n"
                "  void duplicate;",
                1,
            ),
        }
        for label, source in target_factory_source_corruptions.items():
            with self.subTest(label=label):
                source_scan = merge_target_override(source)
                self.assertTrue(
                    checker._query_cache_policy_errors(
                        source_scan,
                        enforce_denominator=True,
                        registry=checker._query_cache_policy_register_from_scan(source_scan),
                    )
                )

        producer_path = checker.QUERY_CACHE_POLICY_GOVERNED_PRODUCER["path"]
        producer_source = (checker.status_checker.REPO_ROOT / producer_path).read_text(
            encoding="utf-8"
        )
        moved_producer_scan = merge_override(
            producer_path,
            producer_source.replace(
                "depthNCycleBoardProjectionQueryOptions",
                "movedDepthNCycleBoardProjectionQueryOptions",
            ),
        )
        self.assertTrue(  # noqa: PT009 - unittest reports the corrupt source payload.
            checker._query_cache_policy_errors(
                moved_producer_scan,
                enforce_denominator=True,
                registry=checker._query_cache_policy_register_from_scan(moved_producer_scan),
            )
        )

        source_sha_flip_scan = merge_target_override(
            target_source.replace(
                "useQuery(options)",
                "useQuery(options!)",
                1,
            )
        )
        self.assertTrue(
            checker._query_cache_policy_errors(
                source_sha_flip_scan,
                enforce_denominator=True,
            )
        )

        health_path = "apps/runtime-dashboard/src/api/hooks/useHealth.ts"
        health_source = (checker.status_checker.REPO_ROOT / health_path).read_text(
            encoding="utf-8"
        )
        inline_to_referenced = merge_override(
            health_path,
            health_source.replace(
                "  return queryOptions({\n"
                "    queryKey: queryKeys.health(),\n"
                "    queryFn: fetchHealth,\n"
                "    staleTime: HEALTH_REFETCH_MS,\n"
                "    refetchInterval: HEALTH_REFETCH_MS,\n"
                "  });",
                "  const existingOptions = {\n"
                "    queryKey: queryKeys.health(),\n"
                "    queryFn: fetchHealth,\n"
                "    staleTime: HEALTH_REFETCH_MS,\n"
                "    refetchInterval: HEALTH_REFETCH_MS,\n"
                "  };\n"
                "  return queryOptions(existingOptions);",
                1,
            ),
        )
        referenced_to_inline = merge_override(
            health_path,
            health_source.replace(
                "  return useQuery(healthQueryOptions());",
                "  return useQuery({\n"
                "    queryKey: queryKeys.health(),\n"
                "    queryFn: fetchHealth,\n"
                "    staleTime: HEALTH_REFETCH_MS,\n"
                "    refetchInterval: HEALTH_REFETCH_MS,\n"
                "  });",
                1,
            ),
        )
        for label, transition_scan, expected_resolution in (
            ("inline_to_referenced", inline_to_referenced, "referenced"),
            ("referenced_to_inline", referenced_to_inline, "inline"),
        ):
            with self.subTest(label=label):
                health_rows = [
                    row
                    for row in transition_scan["queryCachePolicyFacts"]["constructions"]
                    if row["path"] == health_path
                ]
                self.assertTrue(
                    any(row["optionsResolution"] == expected_resolution for row in health_rows)
                )
                self.assertTrue(
                    checker._query_cache_policy_errors(
                        transition_scan,
                        enforce_denominator=True,
                    )
                )

        local_query_lookalike = ts_source(
            """
            function useQuery(options: { queryFn: () => void }) {
              return options;
            }
            useQuery({ queryFn: () => undefined });
            """
        )
        lookalike_scan = checker._enforcement_scan(
            {PROBE_PATH: local_query_lookalike},
            inventory=checker.status_checker._load_json(checker.status_checker.INVENTORY_PATH),
            validate_override_diagnostics=True,
        )
        self.assertEqual([], lookalike_scan["queryCachePolicyFacts"]["constructions"])
        self.assertEqual([], lookalike_scan["queryCachePolicyFacts"]["producers"])

        benign_query_syntax = ts_source(
            """
            function useQuery(options: { queryFn: () => void }) {
              return options;
            }
            function queryOptions(options: { queryFn: () => void }) {
              return options;
            }
            function notAQuery(options: { queryFn: () => void }) {
              return options;
            }
            const standalone = { queryFn: () => undefined };
            useQuery({ queryFn: () => undefined });
            queryOptions({ queryFn: () => undefined });
            notAQuery({ queryFn: () => undefined });
            void standalone;
            """
        )
        benign_scan = checker._enforcement_scan(
            {PROBE_PATH: benign_query_syntax},
            inventory=checker.status_checker._load_json(checker.status_checker.INVENTORY_PATH),
            validate_override_diagnostics=True,
        )
        self.assertEqual([], benign_scan["queryCachePolicyFacts"]["constructions"])
        self.assertEqual([], benign_scan["queryCachePolicyFacts"]["producers"])

        spread_bearing_query_syntax = ts_source(
            """
            import { useQuery } from "@tanstack/react-query";
            import { queryKeys } from "@/api/queryKeys";
            const inherited = { staleTime: 1 };
            useQuery({
              ...inherited,
              queryKey: queryKeys.authMe(),
              queryFn: async () => undefined,
            });
            export function returnedOptions() {
              return {
                ...inherited,
                queryKey: queryKeys.health(),
                queryFn: async () => undefined,
              };
            }
            """
        )
        spread_scan = checker._enforcement_scan(
            {PROBE_PATH: spread_bearing_query_syntax},
            inventory=checker.status_checker._load_json(checker.status_checker.INVENTORY_PATH),
            validate_override_diagnostics=True,
        )
        self.assertEqual(1, len(spread_scan["queryCachePolicyFacts"]["constructions"]))
        self.assertEqual(
            "referenced",
            spread_scan["queryCachePolicyFacts"]["constructions"][0]["optionsResolution"],
        )
        self.assertEqual([], spread_scan["queryCachePolicyFacts"]["producers"])

        spread_without_query_fn = ts_source(
            """
            import { useQuery } from "@tanstack/react-query";
            import { queryKeys } from "@/api/queryKeys";
            const inherited = { staleTime: 1 };
            useQuery({
              ...inherited,
              queryKey: queryKeys.authMe(),
            });
            """
        )
        no_query_fn_spread_scan = checker._enforcement_scan(
            {PROBE_PATH: spread_without_query_fn},
            inventory=checker.status_checker._load_json(checker.status_checker.INVENTORY_PATH),
            validate_override_diagnostics=True,
        )
        self.assertEqual(1, len(no_query_fn_spread_scan["queryCachePolicyFacts"]["constructions"]))
        self.assertEqual(
            "referenced",
            no_query_fn_spread_scan["queryCachePolicyFacts"]["constructions"][0]["optionsResolution"],
        )

        generated_lookalike_path = "apps/runtime-dashboard/src/api/generated/query.ts"
        generated_lookalike_scan = checker._enforcement_scan(
            {
                PROBE_PATH: ts_source(
                    """
                    import { queryOptions, useQuery } from "@/api/generated/query";
                    useQuery({ queryFn: () => undefined });
                    queryOptions({ queryFn: () => undefined });
                    """
                ),
                generated_lookalike_path: ts_source(
                    """
                    export function useQuery(options: { queryFn: () => void }) {
                      return options;
                    }
                    export function queryOptions(options: { queryFn: () => void }) {
                      return options;
                    }
                    """
                ),
            },
            inventory=checker.status_checker._load_json(checker.status_checker.INVENTORY_PATH),
            validate_override_diagnostics=True,
        )
        self.assertEqual(
            [],
            generated_lookalike_scan["queryCachePolicyFacts"]["constructions"],
        )
        self.assertEqual([], generated_lookalike_scan["queryCachePolicyFacts"]["producers"])

        register = checker.status_checker._load_json(checker.QUERY_CACHE_POLICY_REGISTER_PATH)
        corruptions = {
            "added_construction": lambda value: value["constructions"].append(
                copy.deepcopy(value["constructions"][0])
            ),
            "reordered_construction": lambda value: value["constructions"].reverse(),
            "retagged_construction": lambda value: value["constructions"][0].__setitem__(
                "resolved_callee",
                (
                    "useQuery"
                    if value["constructions"][0]["resolved_callee"] == "queryOptions"
                    else "queryOptions"
                ),
            ),
            "untyped_exemption": lambda value: value.__setitem__(
                "exemptions", [{"reason": "trust me"}]
            ),
            "removed_producer": lambda value: value["producers"].pop(),
        }
        for label, corrupt in corruptions.items():
            with self.subTest(label=label):
                mutated = copy.deepcopy(register)
                corrupt(mutated)
                self.assertTrue(
                    checker._query_cache_policy_errors(
                        scan,
                        enforce_denominator=True,
                        registry=mutated,
                    )
                )

    def test_query_construction_options_resolution_is_required_and_nonsemantic(self) -> None:
        """Require every call census row to state only inline or referenced options."""
        errors, scan = checker.validate_enforcement(enforce_authority_escapes=False)
        self.assertEqual([], errors)
        facts = scan["queryCachePolicyFacts"]
        resolutions = [row["optionsResolution"] for row in facts["constructions"]]
        self.assertEqual(66, len(resolutions))
        self.assertEqual({"inline", "referenced"}, set(resolutions))

        register = checker.status_checker._load_json(checker.QUERY_CACHE_POLICY_REGISTER_PATH)
        for label, mutate in {
            "absent": lambda value: value["constructions"][0].pop("options_resolution"),
            "incorrect": lambda value: value["constructions"][0].__setitem__(
                "options_resolution", "unknown"
            ),
        }.items():
            with self.subTest(label=label):
                corrupted = copy.deepcopy(register)
                mutate(corrupted)
                self.assertTrue(
                    checker._query_cache_policy_errors(
                        scan,
                        enforce_denominator=True,
                        registry=corrupted,
                    )
                )

        referenced_call = copy.deepcopy(facts["constructions"][0])
        referenced_call["optionsResolution"] = "referenced"
        enlarged = copy.deepcopy(scan)
        enlarged["queryCachePolicyFacts"]["constructions"].append(referenced_call)
        self.assertTrue(
            checker._query_cache_policy_errors(
                enlarged,
                enforce_denominator=True,
                registry=checker._query_cache_policy_register_from_scan(enlarged),
            )
        )

    def test_full_corruption_probes_exercise_removed_query_producer(self) -> None:
        """Require the executable corruption battery to remove a real producer row."""
        original = checker._query_cache_policy_errors
        removed_producer_registries: list[dict[str, Any]] = []

        def observe_removed_producer(
            scan: dict[str, Any],
            *,
            enforce_denominator: bool = False,
            registry: dict[str, Any] | None = None,
        ) -> list[str]:
            if registry is not None and len(registry.get("producers", [])) == 41:
                removed_producer_registries.append(registry)
            return original(
                scan,
                enforce_denominator=enforce_denominator,
                registry=registry,
            )

        checker._query_cache_policy_errors = observe_removed_producer
        try:
            self.assertEqual([], checker._corruption_probes())
        finally:
            checker._query_cache_policy_errors = original
        self.assertEqual(1, len(removed_producer_registries))

    def test_ds5_closure_corruption_sweep_covers_every_governed_property(
        self,
    ) -> None:
        """Execute every registered corruption owner and prove escapes fail closed."""
        witnesses = (
            (
                "status retirement",
                checker.status_checker,
                ["--check", "--corruption-probes"],
            ),
            (
                "Atlas enforcement",
                checker,
                ["--check", "--corruption-probes"],
            ),
            (
                "frontend disposition and baseline",
                frontend_disposition_checker,
                [
                    "--check",
                    "--verify-baseline-source-bytes",
                    "--corruption-probes",
                ],
            ),
        )

        for label, owner, argv in witnesses:
            with self.subTest(owner=label, phase="live"):
                stdout = StringIO()
                stderr = StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = owner.main(argv)
                self.assertEqual(
                    0,
                    exit_code,
                    f"{label}\nstdout={stdout.getvalue()}\nstderr={stderr.getvalue()}",
                )

        def escaped_corruption(*_args: Any, **_kwargs: Any) -> list[str]:
            return ["c20-synthetic-escape"]

        for label, owner, argv in witnesses:
            with self.subTest(owner=label, phase="remove-property-keep-command"):
                original = owner._corruption_probes
                owner._corruption_probes = escaped_corruption
                try:
                    stdout = StringIO()
                    stderr = StringIO()
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        exit_code = owner.main(argv)
                finally:
                    owner._corruption_probes = original
                self.assertEqual(1, exit_code)
                self.assertIn(
                    "corruption probes escaped: c20-synthetic-escape",
                    stderr.getvalue(),
                )

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
                "current_authored_statuses": 12,
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

    def test_authority_semantic_copy_registry_rejects_identity_bound_corruptions(self) -> None:
        registry = checker.status_checker._load_json(checker.AUTHORITY_SEMANTIC_COPY_REGISTRY_PATH)
        source = (checker.status_checker.REPO_ROOT / AUTHORITY_SEMANTIC_COPY_PATH).read_text(
            encoding="utf-8"
        )
        generated_types = checker.GENERATED_RUNTIME_TYPES_PATH.read_text(encoding="utf-8")

        self.assertEqual(
            [],
            checker._authority_semantic_copy_errors(
                registry=registry,
                source=source,
                generated_types=generated_types,
            ),
        )
        corruptions = {
            "class_upgrade": lambda data: data["copies"][0].__setitem__("strength", "strong"),
            "stale_hash": lambda data: data["copies"][0].__setitem__(
                "content_sha256", "sha256:" + "0" * 64
            ),
            "reviewer": lambda data: data["copies"][0]["review"].__setitem__(
                "reviewer_identity", "external-reviewer:forged"
            ),
            "scope": lambda data: data["copies"][0]["review"].__setitem__(
                "reviewer_scope", "authority-copy.en.unrelated"
            ),
            "duplicate": lambda data: data["copies"].append(copy.deepcopy(data["copies"][0])),
        }
        for label, mutate in corruptions.items():
            with self.subTest(label=label):
                corrupted = copy.deepcopy(registry)
                mutate(corrupted)
                self.assertTrue(
                    checker._authority_semantic_copy_errors(
                        registry=corrupted,
                        source=source,
                        generated_types=generated_types,
                    )
                )

        lookalike = source.replace(
            'AvailableGovernedProjectionPacket["may_not_use_for"][number]',
            'string /* AvailableGovernedProjectionPacket["may_not_use_for"][number] */',
            1,
        )
        self.assertIn(
            "authority_semantic_copy_declaration_identity_drift",
            checker._authority_semantic_copy_errors(
                registry=registry,
                source=lookalike,
                generated_types=generated_types,
            ),
        )

        marker_preserving_bypasses = {
            "missing_weakset_issuance": source.replace(
                "issuedAuthoritySemanticCopies.add(issued);",
                "void issuedAuthoritySemanticCopies;",
                1,
            ),
            "unrelated_weakset_issuance": source.replace(
                "issuedAuthoritySemanticCopies.add(issued);",
                "issuedAuthoritySemanticCopies.add({});",
                1,
            ),
            "unrelated_freeze": source.replace(
                "const issued: AuthoritySemanticCopy = Object.freeze({",
                "const issued: AuthoritySemanticCopy = {",
                1,
            ).replace(
                "  });\n  issuedAuthoritySemanticCopies.add(issued);",
                "  };\n  Object.freeze({});\n  issuedAuthoritySemanticCopies.add(issued);",
                1,
            ),
            "sibling_strong_issuer": source
            + "\nexport function issueStrongAuthoritySemanticCopy(): AuthoritySemanticCopy {\n"
            + '  return issueAuthoritySemanticCopy("phase34.harm.risk.limited", "strong");\n}\n',
        }
        for label, corrupted_source in marker_preserving_bypasses.items():
            with self.subTest(label=label):
                self.assertTrue(
                    checker._authority_semantic_copy_errors(
                        registry=registry,
                        source=corrupted_source,
                        generated_types=generated_types,
                    )
                )

        same_words_different_ids = copy.deepcopy(registry)
        alternate = copy.deepcopy(same_words_different_ids["copies"][0])
        alternate["semantic_id"] = "phase34.harm.risk.limited.alternate"
        same_words_different_ids["copies"].append(alternate)
        self.assertEqual(
            [],
            checker._authority_semantic_copy_errors(
                registry=same_words_different_ids,
                source=source,
                generated_types=generated_types,
            ),
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
