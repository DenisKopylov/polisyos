"""Behavioral tests for the DS4 status-retirement authority guard."""

from __future__ import annotations

import base64
import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ATLAS_DIR = Path(__file__).resolve().parent
CHECKER_PATH = ATLAS_DIR / "check_status_retirement_inventory.py"
INVENTORY_PATH = ATLAS_DIR / "status-retirement-inventory.json"
WAIST_DEBT_PATH = ATLAS_DIR / "ds4-waist-debt-register.json"

C21_INTERACTION_IDS = {
    "semantic-simulation-severity",
    "semantic-quick-insights-panel-level",
    "semantic-insight-callout-insight-level",
}
C21_RETIRED_IDS = {
    "semantic-types-confidence-level",
    "semantic-janus-glyph-janus-glyph-intent",
    "semantic-temporal-capability-banner-tone",
    "semantic-production-slice-retry-profile",
    "semantic-use-chat-store-confidence-level",
    "semantic-compare-tone-81",
    "semantic-compare-tone-86",
    "semantic-outcome-delta-tone",
    "semantic-evidence-sigil-fresc-profile",
    "semantic-confidence-colors",
}
C22_REMAINDER_IDS = {
    "semantic-status-run-badge-kind",
    "semantic-glyph-glyph-intent",
    "semantic-simulation-to-severity",
    "semantic-composer-resolve-launch-badge-kind",
    "semantic-launch-run-resolve-status-kind",
    "semantic-workflow-dag-status-kind",
}

_SPEC = importlib.util.spec_from_file_location("status_retirement_checker", CHECKER_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import bootstrap guard
    raise RuntimeError(f"Unable to import status checker from {CHECKER_PATH}")
checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(checker)


def _artifacts() -> tuple[dict[str, object], dict[str, object]]:
    return (
        json.loads(INVENTORY_PATH.read_text(encoding="utf-8")),
        json.loads(WAIST_DEBT_PATH.read_text(encoding="utf-8")),
    )


class StatusRetirementInventoryTests(unittest.TestCase):
    """Prove the guard recomputes ownership rather than trusting markers."""

    def test_shared_scan_adds_declaration_census_without_changing_ds4_estate(
        self,
    ) -> None:
        inventory, debt = _artifacts()
        scan = checker._scan()

        self.assertEqual(36, scan["sourceDenominators"]["atlasUiProduction"])
        self.assertNotIn("unauthorizedStatusOwners", scan)
        self.assertNotIn("unauthorizedStatusSinks", scan)
        self.assertIsInstance(scan["authoritySinkDeclarations"], list)
        self.assertEqual(
            {
                "current_authored": 12,
                "ds1_rows": 47,
                "semantic_retirement_debt": 0,
            },
            {
                key: checker._summary(inventory, debt)[key]
                for key in (
                    "current_authored",
                    "ds1_rows",
                    "semantic_retirement_debt",
                )
            },
        )

    def test_command_gate_rejects_an_incomplete_generated_receipt_population(
        self,
    ) -> None:
        """The status command consumes the census instead of relying on manual use."""
        with (
            mock.patch.object(checker, "validate_inventory", return_value=[]),
            mock.patch.object(
                checker,
                "build_repository_report",
                return_value={"errors": ["anchor_population_mismatch:probe"]},
            ),
        ):
            self.assertEqual(1, checker.main([]))  # noqa: PT009

    def test_direct_script_entrypoint_resolves_the_receipt_census(self) -> None:
        """The documented path invocation loads the mandatory census bridge."""
        completed = subprocess.run(  # noqa: S603 - fixed interpreter and checker path
            [sys.executable, str(CHECKER_PATH), "--help"],
            cwd=checker.REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)  # noqa: PT009
        self.assertNotIn("ModuleNotFoundError", completed.stderr)  # noqa: PT009

    def test_rejects_a_renamed_local_authority_union(self) -> None:
        inventory, debt = _artifacts()
        errors = checker.validate_inventory(
            inventory,
            debt,
            source_overrides={
                "apps/runtime-dashboard/src/shared/lib/domain/revivedAuthority.ts": (
                    'export type EvidencePosture = "none" | "disputed" '
                    '| "under_review" | "resolved";\n'
                )
            },
        )
        self.assertIn("local_authority_restatement:EvidencePosture", errors)

    def test_rejects_an_inline_authority_synonym(self) -> None:
        inventory, debt = _artifacts()
        errors = checker.validate_inventory(
            inventory,
            debt,
            source_overrides={
                "apps/runtime-dashboard/src/shared/lib/domain/inlineAuthority.ts": (
                    'export interface LocalProjection { verdict: "approved" | "rejected"; }\n'
                )
            },
        )
        self.assertIn("unregistered_status_definition:inlineAuthority.ts:verdict", errors)

    def test_rejects_a_present_but_fake_generated_import(self) -> None:
        inventory, debt = _artifacts()
        errors = checker.validate_inventory(
            inventory,
            debt,
            source_overrides={
                "apps/runtime-dashboard/src/shared/lib/domain/fakeImport.ts": (
                    'import type { VerificationMetadata } from "@polisyos/runtime-api-client";\n'
                    'export type LocalDispute = "none" | "disputed" '
                    '| "under_review" | "resolved";\n'
                    'export type Marker = VerificationMetadata["dispute_status"];\n'
                )
            },
        )
        self.assertIn("local_authority_restatement:LocalDispute", errors)

    def test_rejects_a_sibling_interaction_consumer_in_an_authority_slot(self) -> None:
        inventory, debt = _artifacts()
        errors = checker.validate_inventory(
            inventory,
            debt,
            source_overrides={
                "apps/runtime-dashboard/src/shared/lib/domain/siblingConsumer.ts": (
                    "import { createInteractionState, presentAuthority } "
                    'from "./statusOwnership";\n'
                    'const transport = createInteractionState("ready", "transport");\n'
                    'presentAuthority(transport);\n'
                )
            },
        )
        self.assertIn("interaction_state_reaches_authority_slot:siblingConsumer.ts", errors)

    def test_rejects_missing_duplicate_and_unknown_ds1_joins(self) -> None:
        inventory, debt = _artifacts()
        for mutation_kind in ("missing", "duplicate", "unknown"):
            with self.subTest(mutation_kind=mutation_kind):
                mutation = copy.deepcopy(inventory)
                entries = mutation["entries"]
                if mutation_kind == "missing":
                    entries.pop()
                elif mutation_kind == "duplicate":
                    entries[-1] = copy.deepcopy(entries[0])
                else:
                    entries[-1]["unit_id"] = "status-unknown-c05-probe"
                errors = checker.validate_inventory(mutation, debt, live_probes=False)
                self.assertTrue(
                    any(error.startswith("ds1_status_join_") for error in errors),
                    errors,
                )

    def test_rejects_an_invalid_target_cluster(self) -> None:
        inventory, debt = _artifacts()
        mutation = copy.deepcopy(inventory)
        mutation["entries"][0]["target_cluster"] = "C20"
        errors = checker.validate_inventory(mutation, debt, live_probes=False)
        self.assertTrue(any("target_cluster" in error for error in errors), errors)

    def test_rejects_interaction_without_a_compile_barrier(self) -> None:
        inventory, debt = _artifacts()
        mutation = copy.deepcopy(inventory)
        row = next(
            entry
            for entry in mutation["entries"]
            if entry["classification"] == "interaction_state"
        )
        row.pop("authority_slot_barrier_ref")
        errors = checker.validate_inventory(mutation, debt, live_probes=False)
        self.assertTrue(any("authority_slot_barrier_ref" in error for error in errors), errors)

    def test_schema_admits_continuous_c21_through_c23_targets(self) -> None:
        inventory, debt = _artifacts()
        row = inventory["semantic_exemptions"][0]
        for target in ("C21", "C22", "C22a", "C22b", "C22c", "C22d", "C23"):
            with self.subTest(target=target):
                mutation = copy.deepcopy(inventory)
                mutation_row = next(
                    entry
                    for entry in mutation["semantic_exemptions"]
                    if entry["candidate_id"] == row["candidate_id"]
                )
                mutation_row["target_cluster"] = target
                errors = checker.validate_inventory(
                    mutation, debt, live_probes=False
                )
                self.assertFalse(
                    any(
                        error.startswith("schema:status-retirement-inventory:")
                        and "target_cluster" in error
                        for error in errors
                    ),
                    errors,
                )

    def test_c21_records_the_exact_thirteen_and_leaves_exactly_six_for_c22(
        self,
    ) -> None:
        inventory, debt = _artifacts()
        rows = inventory["semantic_exemptions"]

        self.assertEqual(
            C21_INTERACTION_IDS | C21_RETIRED_IDS,
            {
                row["candidate_id"]
                for row in rows
                if row["target_cluster"] == "C21"
            },
        )
        self.assertEqual(
            C22_REMAINDER_IDS,
            {
                row["candidate_id"]
                for row in rows
                if row["target_cluster"] in checker.C22_SUBCLUSTER_IDS
            },
        )
        self.assertFalse(
            any(row["target_cluster"] == "C23" for row in rows),
            "C23 owns behavioral containment, not a definition row",
        )
        self.assertTrue(
            all(
                row["disposition"] == "interaction_state"
                for row in rows
                if row["candidate_id"] in C21_INTERACTION_IDS
            )
        )
        self.assertTrue(
            all(
                row["current_definition_state"] == "retired"
                for row in rows
                if row["candidate_id"] in C21_RETIRED_IDS
            )
        )
        self.assertEqual(56, len(rows))
        self.assertEqual(47, inventory["denominators"]["ds1_rows"])
        live_c22_rows = {
            row["candidate_id"]
            for row in rows
            if row["target_cluster"] in checker.C22_SUBCLUSTER_IDS
            and row["disposition"] == "retirement_debt"
            and row["current_definition_state"] == "present"
        }
        self.assertEqual(
            len(live_c22_rows),
            checker._summary(inventory, debt)["semantic_retirement_debt"],
        )

    def test_c22_subcluster_partition_is_exact(self) -> None:
        inventory, debt = _artifacts()
        expected = {
            "C22b": frozenset({"semantic-status-run-badge-kind"}),
            "C22c": frozenset({"semantic-glyph-glyph-intent"}),
            "C22d": frozenset(
                {
                    "semantic-simulation-to-severity",
                    "semantic-composer-resolve-launch-badge-kind",
                    "semantic-launch-run-resolve-status-kind",
                    "semantic-workflow-dag-status-kind",
                }
            ),
        }
        self.assertEqual(expected, getattr(checker, "C22_SUBCLUSTER_IDS", {}))
        rows = inventory["semantic_exemptions"]
        for cluster, candidate_ids in expected.items():
            with self.subTest(cluster=cluster):
                self.assertEqual(
                    candidate_ids,
                    {
                        row["candidate_id"]
                        for row in rows
                        if row["target_cluster"] == cluster
                    },
                )
        self.assertFalse(any(row["target_cluster"] == "C22" for row in rows))
        self.assertFalse(any(row["target_cluster"] == "C23" for row in rows))
        live_partition_rows = sum(
            row["current_definition_state"] == "present"
            for row in rows
            if row["target_cluster"] in expected
        )
        self.assertEqual(
            live_partition_rows,
            checker._summary(inventory, debt)["semantic_retirement_debt"],
        )

    def test_c22_remainder_retirement_requires_absent_definition_and_evidence(
        self,
    ) -> None:
        inventory, _debt = _artifacts()
        row = next(
            entry
            for entry in inventory["semantic_exemptions"]
            if entry["candidate_id"] == "semantic-status-run-badge-kind"
        )

        self.assertEqual("retired", row["current_definition_state"])
        retired_c22_rows = sum(
            entry["target_cluster"] in checker.C22_SUBCLUSTER_IDS
            and entry["disposition"] == "retirement_debt"
            and entry["current_definition_state"] == "retired"
            and bool(entry.get("protected_source_paths"))
            and bool(entry.get("verification_refs"))
            for entry in inventory["semantic_exemptions"]
        )
        self.assertEqual(
            inventory["denominators"]["current_total"] - retired_c22_rows,
            checker._summary(inventory, _debt)["current_authored"],
        )
        self.assertNotIn(
            "c22_remainder_disposition_drift:semantic-status-run-badge-kind",
            checker._validate_c21_partition(inventory),
        )

        missing_evidence = copy.deepcopy(inventory)
        missing_evidence_row = next(
            entry
            for entry in missing_evidence["semantic_exemptions"]
            if entry["candidate_id"] == row["candidate_id"]
        )
        missing_evidence_row.pop("protected_source_paths")
        self.assertIn(
            "c22_remainder_disposition_drift:semantic-status-run-badge-kind",
            checker._validate_c21_partition(missing_evidence),
        )

        revived_source = {
            row["source_span"]["path"]: (
                'export type RunBadgeKind = "ok" | "fail" | "warn" '
                '| "unknown";\n'
            )
        }
        self.assertIn(
            "retired_semantic_definition_survives:semantic-status-run-badge-kind",
            checker._validate_source_overrides(inventory, revived_source),
        )

    def test_authored_summary_uses_lifecycle_state_not_candidate_ids(self) -> None:
        inventory, debt = _artifacts()
        baseline = checker._summary(inventory, debt)["current_authored"]
        synthetic = copy.deepcopy(
            next(
                row
                for row in inventory["semantic_exemptions"]
                if row["target_cluster"] == "C22d"
            )
        )
        synthetic["candidate_id"] = "semantic-synthetic-future-retirement"
        synthetic["current_definition_state"] = "retired"
        synthetic["protected_source_paths"] = [
            "apps/runtime-dashboard/src/synthetic/futureRetirement.ts"
        ]
        inventory["semantic_exemptions"].append(synthetic)

        self.assertNotIn(synthetic["candidate_id"], checker.C22_REMAINDER_IDS)
        self.assertEqual(
            baseline - 1,
            checker._summary(inventory, debt)["current_authored"],
        )

    def test_every_retired_semantic_row_drives_generic_revival_protection(
        self,
    ) -> None:
        inventory, _debt = _artifacts()
        mutation = copy.deepcopy(inventory)
        older_row = next(
            row
            for row in mutation["semantic_exemptions"]
            if row["candidate_id"] == "semantic-lineage-freshness"
        )
        older_row["protected_source_paths"] = [
            "apps/runtime-dashboard/src/shared/lib/domain/lineageProbe.ts"
        ]
        expected = [
            {
                "candidateId": row["candidate_id"],
                "members": sorted(row["literal_members"]),
                "paths": sorted(row["protected_source_paths"]),
            }
            for row in mutation["semantic_exemptions"]
            if row["current_definition_state"] == "retired"
            and row.get("protected_source_paths")
        ]

        self.assertEqual(expected, checker._protected_semantic_definitions(mutation))

    def test_c22_behavioral_scanner_rejects_record_map_conditional_synonym_and_fake_owner_import(
        self,
    ) -> None:
        inventory, _debt = _artifacts()
        mutation = copy.deepcopy(inventory)
        row = next(
            entry
            for entry in mutation["semantic_exemptions"]
            if entry["candidate_id"] == "semantic-status-run-badge-kind"
        )
        row["current_definition_state"] = "retired"
        paths = {
            name: f"apps/runtime-dashboard/src/features/runs/domain/c22-{name}.tsx"
            for name in (
                "renamed",
                "record-map",
                "conditional",
                "badge-variable",
                "visual-class",
                "terminal-branch",
                "polling-branch",
                "completed-action",
                "sibling-helper",
                "sibling-consumer",
                "fake-owner",
                "fake-consumer",
                "fake-badge-tone",
                "unresolved-owner",
                "helper-only",
                "inline-owner",
                "object-helper-spread",
                "property-assignment-read",
                "property-assignment-spread",
                "non-jsx-lifecycle",
                "boolean-wrapper",
                "direct-owner-clothing",
                "identity-owner-clothing",
                "aliased-owner-clothing",
                "object-owner-clothing",
                "function-alias-clothing",
                "object-function-alias-clothing",
                "object-owner-spread",
                "inline-owner-spread",
            )
        }
        row["protected_source_paths"] = sorted(paths.values())
        owner_imports = (
            'import type { RunSummary } from "@polisyos/runtime-api-client";\n'
            'import { Badge } from "@polisyos/atlas-ui";\n'
        )
        classifier = (
            "function project(value: RunSummary[\"status\"]) {\n"
            "  return value === 'settled' ? 'stable' : value === 'waiting' ? "
            "'watching' : value === 'denied' ? 'limited' : 'opaque';\n"
            "}\n"
        )
        overrides = {
            paths["renamed"]: (
                owner_imports
                + "function renamed(value: string) {\n"
                + "  if (value === 'a') return 'ok';\n"
                + "  if (value === 'b') return 'fail';\n"
                + "  if (value === 'c') return 'warn';\n"
                + "  return 'unknown';\n}\n"
                + "export const Probe = ({ status }: { status: RunSummary[\"status\"] }) "
                + "=> <Badge kind={renamed(status) as never}>x</Badge>;\n"
            ),
            paths["record-map"]: (
                owner_imports
                + "const TONES: Record<string, string> = { settled: 'stable', "
                + "waiting: 'watching', denied: 'limited' };\n"
                + "function project(value: RunSummary[\"status\"]) { "
                + "return TONES[value] ?? 'opaque'; }\n"
                + "export const Probe = ({ status }: { status: RunSummary[\"status\"] }) "
                + "=> <Badge kind={project(status) as never}>x</Badge>;\n"
            ),
            paths["conditional"]: (
                owner_imports
                + "function project(value: RunSummary[\"status\"]) {\n"
                + "  return value === 'settled' ? 'stable' : value === 'waiting' ? "
                + "'watching' : value === 'denied' ? 'limited' : 'opaque';\n}\n"
                + "export const Probe = ({ status }: { status: RunSummary[\"status\"] }) "
                + "=> <Badge kind={project(status) as never}>x</Badge>;\n"
            ),
            paths["badge-variable"]: (
                owner_imports
                + classifier
                + "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
                + "  const clothing = project(status);\n"
                + "  return <Badge kind={clothing as never}>x</Badge>;\n}\n"
            ),
            paths["visual-class"]: (
                owner_imports
                + classifier
                + "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
                + "  const clothing = project(status);\n"
                + "  return <span className={clothing}>x</span>;\n}\n"
            ),
            paths["terminal-branch"]: (
                owner_imports
                + classifier
                + "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
                + "  const terminal = project(status);\n"
                + "  if (terminal) return <button>stop</button>;\n"
                + "  return null;\n}\n"
            ),
            paths["polling-branch"]: (
                owner_imports
                + classifier
                + "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
                + "  const polling = project(status);\n"
                + "  return polling ? <span>stop polling</span> : <span>poll</span>;\n}\n"
            ),
            paths["completed-action"]: (
                owner_imports
                + classifier
                + "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
                + "  const completed = project(status);\n"
                + "  return <button disabled={!completed}>open result</button>;\n}\n"
            ),
            paths["sibling-helper"]: (
                'import type { RunSummary } from "@polisyos/runtime-api-client";\n'
                + "export function sibling(value: RunSummary[\"status\"]) {\n"
                + "  return value === 'settled' ? 'stable' : 'opaque';\n}\n"
            ),
            paths["sibling-consumer"]: (
                'import { Badge } from "@polisyos/atlas-ui";\n'
                + 'import type { RunSummary } from "@polisyos/runtime-api-client";\n'
                + 'import { sibling } from "./c22-sibling-helper";\n'
                + "export const Probe = ({ status }: { status: RunSummary[\"status\"] }) "
                + "=> <Badge kind={sibling(status) as never}>x</Badge>;\n"
            ),
            paths["fake-owner"]: (
                "export interface RunSummary { status: string }\n"
            ),
            paths["fake-consumer"]: (
                'import { Badge } from "@polisyos/atlas-ui";\n'
                + 'import type { RunSummary } from "./c22-fake-owner";\n'
                + "function project(value: RunSummary[\"status\"]) {\n"
                + "  return value === 'settled' ? 'stable' : 'opaque';\n}\n"
                + "export const Probe = ({ status }: { status: RunSummary[\"status\"] }) "
                + "=> <Badge kind={project(status) as never}>x</Badge>;\n"
            ),
            paths["fake-badge-tone"]: (
                'import type { RunWorkflowNodeView } from "@polisyos/runtime-api-client";\n'
                + 'import { Badge } from "@polisyos/atlas-ui";\n'
                + "type BadgeTone = 'stable' | 'opaque';\n"
                + "function project(value: RunWorkflowNodeView[\"status\"]): BadgeTone {\n"
                + "  return value === 'ok' ? 'stable' : 'opaque';\n}\n"
                + "export const Probe = "
                + "({ status }: { status: RunWorkflowNodeView[\"status\"] }) "
                + "=> <Badge kind={project(status) as never}>x</Badge>;\n"
            ),
            paths["unresolved-owner"]: (
                'import type { MissingOwner } from "@missing/owner";\n'
                + 'import { Badge, type BadgeTone } from "@polisyos/atlas-ui";\n'
                + "function project(value: MissingOwner[\"state\"]): BadgeTone {\n"
                + "  return value === 'settled' ? 'ok' : 'neutral';\n}\n"
                + "export const Probe = "
                + "({ value }: { value: MissingOwner[\"state\"] }) "
                + "=> <Badge kind={project(value)}>x</Badge>;\n"
            ),
            paths["helper-only"]: (
                'import type { RunSummary } from "@polisyos/runtime-api-client";\n'
                + "export function project(value: RunSummary[\"status\"]) {\n"
                + "  return value === 'settled' ? 'stable' : 'opaque';\n}\n"
            ),
            paths["inline-owner"]: (
                'import type { RunSummary } from "@polisyos/runtime-api-client";\n'
                + 'import { Badge } from "@polisyos/atlas-ui";\n'
                + "export const Probe = "
                + "({ status }: { status: RunSummary[\"status\"] }) => "
                + "<Badge kind={(status === 'settled' ? 'ok' : 'neutral') as never}>"
                + "x</Badge>;\n"
            ),
            paths["object-helper-spread"]: (
                owner_imports
                + "function project(value: RunSummary[\"status\"]) {\n"
                + "  return { kind: value === 'settled' ? 'stable' : 'opaque' };\n}\n"
                + "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
                + "  const clothing = project(status);\n"
                + "  return <Badge {...(clothing as never)}>x</Badge>;\n}\n"
            ),
            paths["property-assignment-read"]: (
                owner_imports
                + classifier
                + "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
                + "  const props: { kind?: string } = {};\n"
                + "  props.kind = project(status);\n"
                + "  return <Badge kind={props.kind as never}>x</Badge>;\n}\n"
            ),
            paths["property-assignment-spread"]: (
                owner_imports
                + classifier
                + "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
                + "  const props: { kind?: string } = {};\n"
                + "  props.kind = project(status);\n"
                + "  return <Badge {...(props as never)}>x</Badge>;\n}\n"
            ),
            paths["non-jsx-lifecycle"]: (
                'import type { RunSummary } from "@polisyos/runtime-api-client";\n'
                + "function guessedTerminal(value: RunSummary[\"status\"]) {\n"
                + "  return value === 'settled';\n}\n"
                + "export function refetchInterval(status: RunSummary[\"status\"]) {\n"
                + "  return guessedTerminal(status) ? false : 1000;\n}\n"
            ),
            paths["boolean-wrapper"]: (
                owner_imports
                + classifier
                + "export const Probe = "
                + "({ status }: { status: RunSummary[\"status\"] }) => "
                + "<button disabled={Boolean(project(status))}>open</button>;\n"
            ),
            paths["direct-owner-clothing"]: (
                owner_imports
                + "export const Probe = "
                + "({ status }: { status: RunSummary[\"status\"] }) => "
                + "<Badge kind={status as never}>x</Badge>;\n"
            ),
            paths["identity-owner-clothing"]: (
                owner_imports
                + "function identity<T>(value: T): T { return value; }\n"
                + "export const Probe = "
                + "({ status }: { status: RunSummary[\"status\"] }) => "
                + "<Badge kind={identity(status) as never}>x</Badge>;\n"
            ),
            paths["aliased-owner-clothing"]: (
                owner_imports
                + "type RunStatus = RunSummary[\"status\"];\n"
                + "function project(value: RunStatus) {\n"
                + "  return value === 'settled' ? 'stable' : 'opaque';\n}\n"
                + "export const Probe = ({ status }: { status: RunStatus }) => "
                + "<Badge kind={project(status) as never}>x</Badge>;\n"
            ),
            paths["object-owner-clothing"]: (
                owner_imports
                + "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
                + "  const envelope = { value: status };\n"
                + "  return <Badge kind={envelope.value as never}>x</Badge>;\n}\n"
            ),
            paths["function-alias-clothing"]: (
                owner_imports
                + classifier
                + "const alias = project;\n"
                + "export const Probe = "
                + "({ status }: { status: RunSummary[\"status\"] }) => "
                + "<Badge kind={alias(status) as never}>x</Badge>;\n"
            ),
            paths["object-function-alias-clothing"]: (
                owner_imports
                + classifier
                + "const adapters = { project };\n"
                + "export const Probe = "
                + "({ status }: { status: RunSummary[\"status\"] }) => "
                + "<Badge kind={adapters.project(status) as never}>x</Badge>;\n"
            ),
            paths["object-owner-spread"]: (
                owner_imports
                + "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
                + "  const props = { kind: status };\n"
                + "  return <Badge {...(props as never)}>x</Badge>;\n}\n"
            ),
            paths["inline-owner-spread"]: (
                owner_imports
                + "export const Probe = "
                + "({ status }: { status: RunSummary[\"status\"] }) => "
                + "<Badge {...({ kind: status } as never)}>x</Badge>;\n"
            ),
        }

        scan = checker._scan(overrides, inventory=mutation)
        rejected_paths = {
            revival["path"] for revival in scan.get("protectedRevivals", [])
        }
        expected_consumers = {
            path
            for name, path in paths.items()
            if name not in {"sibling-helper", "fake-owner", "helper-only"}
        }
        self.assertEqual(expected_consumers, rejected_paths)

    def test_c22_behavioral_scanner_allows_generated_indexed_owner_types_and_badge_tone(
        self,
    ) -> None:
        inventory, _debt = _artifacts()
        mutation = copy.deepcopy(inventory)
        row = next(
            entry
            for entry in mutation["semantic_exemptions"]
            if entry["candidate_id"] == "semantic-status-run-badge-kind"
        )
        row["current_definition_state"] = "retired"
        source_path = (
            "apps/runtime-dashboard/src/features/runs/domain/"
            "c22-generated-owner-positive.tsx"
        )
        raw_path = (
            "apps/runtime-dashboard/src/features/runs/domain/"
            "c22-raw-owner-label-positive.tsx"
        )
        layout_path = (
            "apps/runtime-dashboard/src/features/runs/domain/"
            "c22-layout-positive.tsx"
        )
        constant_path = (
            "apps/runtime-dashboard/src/features/runs/domain/"
            "c22-constant-helper-positive.tsx"
        )
        logging_path = (
            "apps/runtime-dashboard/src/features/runs/domain/"
            "c22-logging-positive.tsx"
        )
        observation_assignment_path = (
            "apps/runtime-dashboard/src/features/runs/domain/"
            "c22-observation-assignment-positive.tsx"
        )
        children_spread_path = (
            "apps/runtime-dashboard/src/features/runs/domain/"
            "c22-children-spread-positive.tsx"
        )
        row["protected_source_paths"] = [
            source_path,
            raw_path,
            layout_path,
            constant_path,
            logging_path,
            observation_assignment_path,
            children_spread_path,
        ]
        source = (
            'import type { RunWorkflowNodeView } from "@polisyos/runtime-api-client";\n'
            'import { Badge, type BadgeTone } from "@polisyos/atlas-ui";\n'
            "const TONES: Record<RunWorkflowNodeView[\"status\"], BadgeTone> = {\n"
            "  ok: 'ok', skip: 'neutral', fail: 'fail', unknown: 'neutral',\n"
            "};\n"
            "function tone(status: RunWorkflowNodeView[\"status\"]): BadgeTone {\n"
            "  return TONES[status];\n"
            "}\n"
            "export const Probe = "
            "({ status }: { status: RunWorkflowNodeView[\"status\"] }) => "
            "<Badge kind={tone(status)}>x</Badge>;\n"
        )

        raw_source = (
            'import type { RunSummary } from "@polisyos/runtime-api-client";\n'
            "function raw(value: RunSummary[\"status\"]) { return value; }\n"
            "export const Probe = "
            "({ status }: { status: RunSummary[\"status\"] }) => "
            "<code>{raw(status)}</code>;\n"
        )
        layout_source = (
            "function layout(width: number) {\n"
            "  if (width > 1200) return 'grid-cols-3';\n"
            "  if (width > 800) return 'grid-cols-2';\n"
            "  return 'grid-cols-1';\n"
            "}\n"
            "export const Probe = ({ width }: { width: number }) => "
            "<span className={layout(width)}>x</span>;\n"
        )
        constant_source = (
            'import type { RunSummary } from "@polisyos/runtime-api-client";\n'
            'import { Badge } from "@polisyos/atlas-ui";\n'
            "function project(value: RunSummary[\"status\"]) {\n"
            "  return value === 'settled' ? 'stable' : 'opaque';\n"
            "}\n"
            "export const Probe = () => "
            "<Badge kind={project('settled') as never}>x</Badge>;\n"
        )
        logging_source = (
            'import type { RunSummary } from "@polisyos/runtime-api-client";\n'
            "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
            "  if (status === 'settled') console.debug(status);\n"
            "  return <span>static</span>;\n"
            "}\n"
        )
        observation_assignment_source = (
            'import type { RunSummary } from "@polisyos/runtime-api-client";\n'
            "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
            "  let observed = '';\n"
            "  if (status === 'settled') observed = status;\n"
            "  console.debug(observed);\n"
            "  return <span>static</span>;\n"
            "}\n"
        )
        children_spread_source = (
            'import type { RunSummary } from "@polisyos/runtime-api-client";\n'
            "export function Probe({ status }: { status: RunSummary[\"status\"] }) {\n"
            "  const props = { children: status };\n"
            "  return <code {...props} />;\n"
            "}\n"
        )
        scan = checker._scan(
            {
                source_path: source,
                raw_path: raw_source,
                layout_path: layout_source,
                constant_path: constant_source,
                logging_path: logging_source,
                observation_assignment_path: observation_assignment_source,
                children_spread_path: children_spread_source,
            },
            inventory=mutation,
        )

        self.assertEqual([], scan.get("protectedRevivals", []))

    def test_rejects_semantic_interaction_state_without_an_authority_barrier(
        self,
    ) -> None:
        inventory, debt = _artifacts()
        mutation = copy.deepcopy(inventory)
        row = next(
            entry
            for entry in mutation["semantic_exemptions"]
            if entry["disposition"] == "interaction_state"
        )
        row.pop("authority_slot_barrier_ref")

        errors = checker.validate_inventory(mutation, debt, live_probes=False)

        self.assertTrue(
            any("authority_slot_barrier_ref" in error for error in errors), errors
        )

    def test_inventory_generated_c21_revival_variants_fail_closed(self) -> None:
        inventory, debt = _artifacts()
        row = next(
            entry
            for entry in inventory["semantic_exemptions"]
            if entry["candidate_id"] == "semantic-types-confidence-level"
        )
        members = list(row["literal_members"])
        literal_union = " | ".join(repr(member) for member in members)
        reversed_union = "\n  | ".join(repr(member) for member in reversed(members))
        literal_array = ", ".join(repr(member) for member in members)
        source_path = row["source_span"]["path"]
        probes = {
            "renamed_union": f"export type OpaqueVocabulary = {literal_union};\n",
            "alias_indirection": (
                f"type HiddenVocabulary = {literal_union};\n"
                "export type OpaqueAlias = HiddenVocabulary;\n"
            ),
            "reordered_reformatted_union": (
                f"export type OpaqueVocabulary =\n  | {reversed_union};\n"
            ),
            "inline_reconstruction": (
                f"export interface Probe {{ mode: {literal_union}; }}\n"
            ),
            "const_reconstruction": (
                f"export const OPAQUE_VOCABULARY = [{literal_array}] as const;\n"
            ),
            "helper_reconstruction": (
                "export function classify(value: number) {\n"
                f"  if (value > 0.8) return {members[0]!r};\n"
                f"  if (value > 0.5) return {members[1]!r};\n"
                f"  return {members[2]!r};\n"
                "}\n"
            ),
            "sibling_consumer_reclassification": (
                "export const PRESENTATION = {\n"
                + "\n".join(
                    f"  value{index}: {member!r},"
                    for index, member in enumerate(members)
                )
                + "\n} as const;\n"
            ),
        }

        for name, source in probes.items():
            with self.subTest(name=name):
                errors = checker.validate_inventory(
                    inventory,
                    debt,
                    source_overrides={source_path: source},
                    live_probes=False,
                )
                self.assertTrue(
                    any(
                        error.startswith("retired_semantic_definition_survives:")
                        or error.startswith("unregistered_semantic_definition:")
                        for error in errors
                    ),
                    errors,
                )

    def test_inventory_generated_c21_synonym_helper_revival_fails_closed(
        self,
    ) -> None:
        inventory, debt = _artifacts()
        row = next(
            entry
            for entry in inventory["semantic_exemptions"]
            if entry["candidate_id"] == "semantic-types-confidence-level"
        )
        source_path = next(
            path
            for path in row["protected_source_paths"]
            if path.endswith("FrequencyDots.tsx")
        )
        label_pool = ("strong", "moderate", "weak", "opaque")
        labels = [
            label_pool[index] for index, _ in enumerate(row["literal_members"])
        ]
        branches = "".join(
            f"  if (value > {8 - index * 3} / 10) return {label!r};\n"
            for index, label in enumerate(labels[:-1])
        )
        classifier = (
            "function choose(value: number) {\n"
            f"{branches}"
            f"  return {labels[-1]!r};\n"
            "}\n"
        )
        revivals = {
            "direct": (
                f"{classifier}"
                "export function Probe({ value }: { value: number }) {\n"
                "  const result = choose(value);\n"
                "  return <span className={result}>x</span>;\n"
                "}\n"
            ),
            "wrapper_return": (
                f"{classifier}"
                "function clothing(value: number) { return choose(value); }\n"
                "export function Probe({ value }: { value: number }) {\n"
                "  return <span className={clothing(value)}>x</span>;\n"
                "}\n"
            ),
            "later_assignment": (
                f"{classifier}"
                "export function Probe({ value }: { value: number }) {\n"
                "  let result = '';\n"
                "  result = choose(value);\n"
                "  return <span className={result}>x</span>;\n"
                "}\n"
            ),
            "jsx_spread": (
                f"{classifier}"
                "export function Probe({ value }: { value: number }) {\n"
                "  const props = { className: choose(value) };\n"
                "  return <span {...props}>x</span>;\n"
                "}\n"
            ),
            "object_indirected_labels": (
                "const labels = {\n"
                + ",\n".join(
                    f"  value{index}: {label!r}"
                    for index, label in enumerate(labels)
                )
                + "\n};\n"
                "function choose(value: number) {\n"
                + "".join(
                    f"  if (value > {8 - index * 3} / 10) "
                    f"return labels.value{index};\n"
                    for index in range(len(labels) - 1)
                )
                + f"  return labels.value{len(labels) - 1};\n"
                "}\n"
                "export function Probe({ value }: { value: number }) {\n"
                "  return <span className={choose(value)}>x</span>;\n"
                "}\n"
            ),
            "sink_class_composition": (
                f"{classifier}"
                "declare function cx(...values: string[]): string;\n"
                "export function Probe({ value }: { value: number }) {\n"
                "  return <span className={cx('p-2', choose(value))}>x</span>;\n"
                "}\n"
            ),
            "helper_class_composition": (
                "declare function cx(...values: string[]): string;\n"
                "function choose(value: number) {\n"
                "  return cx(\n"
                "    'p-2',\n"
                f"    value > 0.8 ? {labels[0]!r} : "
                f"value > 0.5 ? {labels[1]!r} : {labels[2]!r},\n"
                "  );\n"
                "}\n"
                "export function Probe({ value }: { value: number }) {\n"
                "  return <span className={choose(value)}>x</span>;\n"
                "}\n"
            ),
            "conditional_branch_class_composition": (
                "declare function cx(...values: string[]): string;\n"
                "function choose(value: number) {\n"
                "  return value > 0.8\n"
                f"    ? cx('p-2', {labels[0]!r})\n"
                "    : value > 0.5\n"
                f"      ? cx('p-2', {labels[1]!r})\n"
                f"      : cx('p-2', {labels[2]!r});\n"
                "}\n"
                "export function Probe({ value }: { value: number }) {\n"
                "  return <span className={choose(value)}>x</span>;\n"
                "}\n"
            ),
        }

        for name, source in revivals.items():
            with self.subTest(name=name):
                errors = checker.validate_inventory(
                    inventory,
                    debt,
                    source_overrides={source_path: source},
                    live_probes=False,
                )
                self.assertIn(
                    "retired_semantic_definition_survives:semantic-types-confidence-level",
                    errors,
                )

        responsive_layout = (
            "function layout(width: number) {\n"
            "  if (width > 1200) return 'grid-cols-3';\n"
            "  if (width > 800) return 'grid-cols-2';\n"
            "  return 'grid-cols-1';\n"
            "}\n"
            "export function Probe({ width }: { width: number }) {\n"
            "  return <span className={layout(width)}>x</span>;\n"
            "}\n"
        )
        layout_errors = checker.validate_inventory(
            inventory,
            debt,
            source_overrides={source_path: responsive_layout},
            live_probes=False,
        )
        self.assertFalse(
            any(
                error.startswith("retired_semantic_definition_survives:")
                for error in layout_errors
            ),
            layout_errors,
        )

    def test_source_flip_rejects_every_protected_c21_retired_owner(self) -> None:
        inventory, debt = _artifacts()
        rows = [
            row
            for row in inventory["semantic_exemptions"]
            if row["candidate_id"] in C21_RETIRED_IDS
        ]
        self.assertEqual(C21_RETIRED_IDS, {row["candidate_id"] for row in rows})

        for row in rows:
            with self.subTest(candidate_id=row["candidate_id"]):
                members = list(row["literal_members"])
                literal_array = ", ".join(repr(member) for member in members)
                source = (
                    "export const REVIVED_VOCABULARY = "
                    f"[{literal_array}] as const;\n"
                )
                errors = checker.validate_inventory(
                    inventory,
                    debt,
                    source_overrides={row["source_span"]["path"]: source},
                    live_probes=False,
                )
                self.assertTrue(
                    f"retired_semantic_definition_survives:{row['candidate_id']}"
                    in errors
                    or any(
                        error.startswith("unregistered_semantic_definition:")
                        for error in errors
                    ),
                    errors,
                )

    def test_rejects_a_removed_row_whose_source_survives(self) -> None:
        inventory, debt = _artifacts()
        mutation = copy.deepcopy(inventory)
        row = next(
            entry
            for entry in mutation["entries"]
            if entry["unit_id"] == "status-collaboration-session"
        )
        row["source_span"]["path"] = (
            "apps/runtime-dashboard/src/shared/lib/domain/statusOwnership.ts"
        )
        errors = checker.validate_inventory(mutation, debt)
        self.assertIn("removed_source_survives:status-collaboration-session", errors)

    def test_allows_a_retired_definition_when_its_owner_file_remains(self) -> None:
        inventory, _debt = _artifacts()
        row = next(
            entry
            for entry in inventory["entries"]
            if entry["unit_id"] == "status-quantity-provenance"
        )

        source = Path(row["source_span"]["path"])
        self.assertEqual("retired", row["current_definition_state"])
        self.assertTrue((checker.REPO_ROOT / source).exists())
        errors = checker._validate_live_scan(inventory, checker._scan())

        self.assertEqual([], errors)

    def test_rejects_a_revived_retired_semantic_definition(self) -> None:
        inventory, debt = _artifacts()
        row = next(
            entry
            for entry in inventory["semantic_exemptions"]
            if entry["candidate_id"] == "semantic-lineage-freshness"
        )
        self.assertEqual("retired", row["current_definition_state"])
        errors = checker.validate_inventory(
            inventory,
            debt,
            source_overrides={
                row["source_span"]["path"]: (
                    'export type LineageFreshness = "current" | "stale" | "unknown";\n'
                )
            },
        )

        self.assertIn(
            "unregistered_status_definition:quantity.types.ts:LineageFreshness",
            errors,
        )

    def test_rejects_same_set_binding_to_the_wrong_generated_field(self) -> None:
        inventory, debt = _artifacts()
        mutation = copy.deepcopy(inventory)
        row = next(
            entry
            for entry in mutation["entries"]
            if entry["unit_id"] == "status-scenario"
        )
        row["owner_type"]["query"] = 'VerificationMetadata["verification_status"]'
        errors = checker.validate_inventory(mutation, debt, live_probes=False)
        self.assertIn("generated_query_drift:status-scenario", errors)

    def test_rejects_a_self_consistent_anchor_that_misstates_the_local_source_owner(self) -> None:
        inventory, debt = _artifacts()
        mutation = copy.deepcopy(inventory)
        row = next(
            entry
            for entry in mutation["entries"]
            if entry["unit_id"] == "status-verification"
        )
        row["owner_type"]["query"] = 'VerificationMetadata["verification_status"]'
        row["generated_anchor"].update(
            {
                "export_symbol": "VerificationMetadata",
                "canonical_line": 1000,
                "schema_line": 10334,
                "field": "verification_status",
            }
        )

        errors = checker.validate_inventory(mutation, debt, live_probes=False)

        self.assertIn("generated_source_binding_drift:status-verification", errors)

    def test_rejects_denominator_drift_but_lines_only_navigate(self) -> None:
        inventory, debt = _artifacts()
        denominator_mutation = copy.deepcopy(inventory)
        denominator_mutation["denominators"]["current_total"] = 47
        errors = checker.validate_inventory(denominator_mutation, debt, live_probes=False)
        self.assertIn("current_denominator_drift", errors)

        anchor_mutation = copy.deepcopy(inventory)
        row = next(
            entry
            for entry in anchor_mutation["entries"]
            if entry["unit_id"] == "status-scenario"
        )
        row["generated_anchor"]["canonical_line"] = 1
        row["generated_anchor"]["schema_line"] = 1
        errors = checker.validate_inventory(anchor_mutation, debt, live_probes=False)
        self.assertFalse(
            any(error.startswith("generated_anchor_drift:") for error in errors),
            errors,
        )

        identity_mutation = copy.deepcopy(inventory)
        identity_row = next(
            entry
            for entry in identity_mutation["entries"]
            if entry["unit_id"] == "status-scenario"
        )
        anchor = identity_row["generated_anchor"]
        anchor["canonical_identity"], anchor["schema_identity"] = (
            anchor["schema_identity"],
            anchor["canonical_identity"],
        )
        errors = checker.validate_inventory(identity_mutation, debt, live_probes=False)
        self.assertTrue(
            any(error.startswith("anchor_identity_slot_drift:") for error in errors),
            errors,
        )

        hidden_navigation_mutation = copy.deepcopy(inventory)
        hidden_row = next(
            entry
            for entry in hidden_navigation_mutation["entries"]
            if entry["unit_id"] == "status-scenario"
        )
        encoded_identity = hidden_row["generated_anchor"]["schema_identity"]
        source_path, encoded_payload = encoded_identity.split("#ts-identity=", 1)
        payload = json.loads(
            base64.urlsafe_b64decode(
                encoded_payload + "=" * (-len(encoded_payload) % 4)
            )
        )
        payload["navigation_hint"] = hidden_row["generated_anchor"]["schema_line"]
        hidden_row["generated_anchor"]["schema_identity"] = (
            source_path
            + "#ts-identity="
            + base64.urlsafe_b64encode(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            )
            .decode("ascii")
            .rstrip("=")
        )
        errors = checker.validate_inventory(
            hidden_navigation_mutation, debt, live_probes=False
        )
        self.assertTrue(
            any(
                "typescript_reference_identity_invalid" in error for error in errors
            ),
            errors,
        )

    def test_generated_anchor_accepts_only_retired_historical_source_absence(self) -> None:
        inventory, debt = _artifacts()
        historical = next(
            entry
            for entry in inventory["entries"]
            if entry["unit_id"] == "status-inline-readiness-gate"
        )
        self.assertEqual("retired", historical["current_definition_state"])
        self.assertNotIn(
            "generated_source_missing:status-inline-readiness-gate",
            checker.validate_inventory(inventory, debt, live_probes=False),
        )

        mutation = copy.deepcopy(inventory)
        row = next(
            entry
            for entry in mutation["entries"]
            if entry["unit_id"] == "status-inline-readiness-gate"
        )
        row["current_definition_state"] = "present"
        errors = checker.validate_inventory(mutation, debt, live_probes=False)

        self.assertIn("generated_source_missing:status-inline-readiness-gate", errors)

    def test_rejects_a_fourth_waist_row_or_non_ds5_owner(self) -> None:
        inventory, debt = _artifacts()
        fourth = copy.deepcopy(debt)
        fourth["entries"].append(copy.deepcopy(fourth["entries"][0]))
        fourth["entries"][-1]["debt_id"] = "ds4-waist-fourth-probe"
        errors = checker.validate_inventory(inventory, fourth, live_probes=False)
        self.assertIn("waist_debt_count:4", errors)

        wrong_owner = copy.deepcopy(debt)
        wrong_owner["entries"][0]["owner"] = "DS4"
        errors = checker.validate_inventory(inventory, wrong_owner, live_probes=False)
        self.assertIn("waist_debt_owner:ds4-waist-cgf-disposition", errors)

    def test_rejects_non_exact_generated_schema_spans_for_present_waist_anchors(
        self,
    ) -> None:
        inventory, debt = _artifacts()
        present_ids = {
            entry["debt_id"]
            for entry in debt["entries"]
            if entry["generated_client_anchor"]["anchor_kind"]
            == "present_projection"
        }

        for debt_id in present_ids:
            for field in ("types_start_line", "types_end_line"):
                with self.subTest(debt_id=debt_id, field=field):
                    mutation = copy.deepcopy(debt)
                    row = next(
                        entry
                        for entry in mutation["entries"]
                        if entry["debt_id"] == debt_id
                    )
                    row["generated_client_anchor"][field] += 1

                    errors = checker.validate_inventory(
                        inventory,
                        mutation,
                        live_probes=False,
                    )

                    self.assertIn(f"waist_debt_anchor_drift:{debt_id}", errors)

    def test_rejects_an_unregistered_semantic_union_outside_the_status_denominator(self) -> None:
        inventory, debt = _artifacts()
        mutation = copy.deepcopy(inventory)
        removed = next(
            entry
            for entry in mutation["semantic_exemptions"]
            if entry["current_definition_state"] == "present"
            and entry["source_span"].get("declaration_name")
        )
        mutation["semantic_exemptions"].remove(removed)

        errors = checker.validate_inventory(mutation, debt)

        self.assertIn(
            "unregistered_semantic_definition:"
            + removed["source_span"]["declaration_name"],
            errors,
        )

    def test_scan_routes_authority_like_confidence_and_severity_unions_to_semantic_candidates(
        self,
    ) -> None:
        scan = checker._scan(
            {
                "apps/runtime-dashboard/src/shared/lib/domain/semanticProbe.ts": (
                    'export type ConfidenceLadderRung = "low" | "high";\n'
                    'export type RunBadgeKind = "success" | "failure";\n'
                    'export interface Probe { severity: "low" | "high"; }\n'
                )
            }
        )

        candidates = {
            fact.get("declarationName") or fact.get("fieldName")
            for fact in scan["authorityCandidates"]
        }
        self.assertEqual(
            {"ConfidenceLadderRung", "RunBadgeKind", "severity"}, candidates
        )

    def test_scan_rejects_authority_like_function_and_method_return_unions(
        self,
    ) -> None:
        inventory, debt = _artifacts()

        errors = checker.validate_inventory(
            inventory,
            debt,
            source_overrides={
                "apps/runtime-dashboard/src/shared/lib/domain/returnVocabulary.ts": (
                    "export function projectionVerdict(): "
                    '"admissible" | "blocked" { return "blocked"; }\n'
                    "export class ProjectionPresenter {\n"
                    "  authorityTone(): "
                    '"ok" | "fail" { return "fail"; }\n'
                    "}\n"
                )
            },
            live_probes=False,
        )

        self.assertIn(
            "unregistered_semantic_definition:projectionVerdict",
            errors,
        )
        self.assertIn(
            "unregistered_semantic_definition:authorityTone",
            errors,
        )

    def test_live_scan_rejects_an_interaction_state_reaching_an_authority_slot(
        self,
    ) -> None:
        inventory, _debt = _artifacts()
        scan = copy.deepcopy(checker._scan())
        scan["interactionLeaks"].append(
            {
                "path": "apps/runtime-dashboard/src/shared/lib/domain/liveLeak.ts",
                "line": 7,
            }
        )

        errors = checker._validate_live_scan(inventory, scan)

        self.assertIn("interaction_state_reaches_authority_slot:liveLeak.ts", errors)

    def test_scan_rejects_a_nullable_semantic_string_vocabulary(self) -> None:
        inventory, debt = _artifacts()

        errors = checker.validate_inventory(
            inventory,
            debt,
            source_overrides={
                "apps/runtime-dashboard/src/shared/lib/domain/nullableGrade.ts": (
                    'export type DecisionGrade = "pass" | "fail" | null;\n'
                )
            },
            live_probes=False,
        )

        self.assertIn(
            "unregistered_status_definition:nullableGrade.ts:DecisionGrade",
            errors,
        )

    def test_scan_rejects_an_as_const_semantic_vocabulary(self) -> None:
        inventory, debt = _artifacts()

        errors = checker.validate_inventory(
            inventory,
            debt,
            source_overrides={
                "apps/runtime-dashboard/src/shared/lib/domain/gradeVocabulary.ts": (
                    "export const DecisionGradeVocabulary = "
                    '["pass", "fail"] as const;\n'
                )
            },
            live_probes=False,
        )

        self.assertIn(
            "unregistered_semantic_definition:DecisionGradeVocabulary",
            errors,
        )

    def test_scan_rejects_aliased_interaction_factory_and_authority_sink(self) -> None:
        inventory, debt = _artifacts()

        errors = checker.validate_inventory(
            inventory,
            debt,
            source_overrides={
                "apps/runtime-dashboard/src/shared/lib/domain/aliasedLeak.ts": (
                    "import { createInteractionState as makeInteraction, "
                    "presentAuthority as showAuthority } "
                    'from "./statusOwnership";\n'
                    'const transport = makeInteraction("ready", "transport");\n'
                    "showAuthority(transport);\n"
                )
            },
            live_probes=False,
        )

        self.assertIn(
            "interaction_state_reaches_authority_slot:aliasedLeak.ts",
            errors,
        )

    def test_scan_rejects_an_interaction_state_returned_by_a_helper(self) -> None:
        inventory, debt = _artifacts()

        errors = checker.validate_inventory(
            inventory,
            debt,
            source_overrides={
                "apps/runtime-dashboard/src/shared/lib/domain/helperLeak.ts": (
                    "import { createInteractionState, presentAuthority } "
                    'from "./statusOwnership";\n'
                    "function interactionForAuthority() {\n"
                    '  return createInteractionState("ready", "transport");\n'
                    "}\n"
                    "presentAuthority(interactionForAuthority());\n"
                )
            },
            live_probes=False,
        )

        self.assertIn(
            "interaction_state_reaches_authority_slot:helperLeak.ts",
            errors,
        )

    def test_summary_counts_only_live_semantic_retirement_debt(self) -> None:
        inventory, debt = _artifacts()
        expected = sum(
            row["disposition"] == "retirement_debt"
            and row["current_definition_state"] == "present"
            for row in inventory["semantic_exemptions"]
        )

        self.assertEqual(
            expected,
            checker._summary(inventory, debt)["semantic_retirement_debt"],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
