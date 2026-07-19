"""Behavioral tests for the DS4 status-retirement authority guard."""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ATLAS_DIR = Path(__file__).resolve().parent
CHECKER_PATH = ATLAS_DIR / "check_status_retirement_inventory.py"
INVENTORY_PATH = ATLAS_DIR / "status-retirement-inventory.json"
WAIST_DEBT_PATH = ATLAS_DIR / "ds4-waist-debt-register.json"

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

    def test_rejects_denominator_and_generated_anchor_drift(self) -> None:
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
        row["generated_anchor"]["schema_line"] = 1
        errors = checker.validate_inventory(anchor_mutation, debt, live_probes=False)
        self.assertIn("generated_anchor_drift:status-scenario", errors)

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

    def test_rejects_an_unregistered_semantic_union_outside_the_status_denominator(self) -> None:
        inventory, debt = _artifacts()
        mutation = copy.deepcopy(inventory)
        mutation["semantic_exemptions"] = []

        errors = checker.validate_inventory(mutation, debt)

        self.assertIn(
            "unregistered_semantic_definition:LineageFreshness",
            errors,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
