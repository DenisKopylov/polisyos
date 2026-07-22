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
        for target in ("C21", "C22", "C23"):
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
                if row["target_cluster"] == "C22"
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
        self.assertEqual(55, len(rows))
        self.assertEqual(47, inventory["denominators"]["ds1_rows"])
        self.assertEqual(6, checker._summary(inventory, debt)["semantic_retirement_debt"])

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
        row["generated_anchor"] = {
            "export_symbol": "VerificationMetadata",
            "canonical_line": 1000,
            "schema_line": 10334,
            "field": "verification_status",
        }

        errors = checker.validate_inventory(mutation, debt, live_probes=False)

        self.assertIn("generated_source_binding_drift:status-verification", errors)

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
