"""Focused behavioral tests for the Atlas frontend disposition checker."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from typing import ClassVar
from unittest import mock

ATLAS_DIR = Path(__file__).resolve().parent
CHECKER_PATH = ATLAS_DIR / "check_frontend_disposition_register.py"
REGISTER_PATH = ATLAS_DIR / "frontend-disposition-register.json"

_SPEC = importlib.util.spec_from_file_location("frontend_disposition_checker", CHECKER_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import bootstrap guard
    raise RuntimeError(f"Unable to import disposition checker from {CHECKER_PATH}")
checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(checker)


def _mixed_receipt(*, retired: int = 3) -> dict[str, object]:
    return {
        "receipt_id": "ds4-c03b-ui-primitives-mixed-disposition",
        "kind": "aggregate_mixed_disposition",
        "reason": "no_production_consumer",
        "counts": {
            "total": 29,
            "package_migrated": 22,
            "dashboard_rebound": 2,
            "retired": retired,
            "use_as_is": 2,
            "c03b_candidates": 5,
            "production_consumers": 0,
        },
        "c03b_members": [
            {
                "primitive": "DropdownMenu",
                "disposition": "retire",
                "ds2_adoption_id": None,
                "governing_condition": None,
                "ledger_absence_reason": "no_exact_ds2_row",
            },
            {
                "primitive": "ScrollArea",
                "disposition": "use_as_is",
                "ds2_adoption_id": "component-scroll-area",
                "governing_condition": (
                    "Archive admission alone sunsets nothing. DS4 may remove a mapped loser "
                    "only after generated/source ownership, consumer migration, drift checks, "
                    "and the owning slice's DS6 evidence are complete."
                ),
                "ledger_absence_reason": None,
            },
            {
                "primitive": "Separator",
                "disposition": "retire",
                "ds2_adoption_id": None,
                "governing_condition": None,
                "ledger_absence_reason": "no_exact_ds2_row",
            },
            {
                "primitive": "Sheet",
                "disposition": "retire",
                "ds2_adoption_id": None,
                "governing_condition": None,
                "ledger_absence_reason": "no_exact_ds2_row",
            },
            {
                "primitive": "Tabs",
                "disposition": "use_as_is",
                "ds2_adoption_id": "component-tabs",
                "governing_condition": (
                    "Keep the mapped live v4 family as the transitional winner until DS4 "
                    "routes a real consumer through one governed replacement, DS6 passes its "
                    "negative/browser/accessibility evidence, and the old import path is removed."
                ),
                "ledger_absence_reason": None,
            },
        ],
        "reference_census_id": "census-ds4-c03b-dormant-primitives",
        "pre_deletion_resurrection_anchor": {
            "git_commit": "caa1ee6e3ab49d559b19dbeeda6308c3598e7183",
            "files": [
                {
                    "path": "apps/runtime-dashboard/src/shared/ui/DropdownMenu.tsx",
                    "git_blob": "7bf4bfc423f17393ac1f8646e94d0da8b8d0c8a6",
                },
                {
                    "path": "apps/runtime-dashboard/src/shared/ui/DropdownMenu.a11y.test.tsx",
                    "git_blob": "67e09a12bef1f1fe0b996dcdbc151bc9f8ee8a33",
                },
                {
                    "path": "apps/runtime-dashboard/src/shared/ui/Separator.tsx",
                    "git_blob": "de156b91bb009e287df0e3fda6f70ae21364bd13",
                },
                {
                    "path": "apps/runtime-dashboard/src/shared/ui/Separator.a11y.test.tsx",
                    "git_blob": "1da3670349e6b31b832c1fa5ee236d58ff57eab6",
                },
                {
                    "path": "apps/runtime-dashboard/src/shared/ui/Sheet.tsx",
                    "git_blob": "c119e917a73c942e2c2b00a03b84b7c3d86b6d5e",
                },
                {
                    "path": "apps/runtime-dashboard/src/shared/ui/Sheet.a11y.test.tsx",
                    "git_blob": "5b4f8d67e39bd31869ebe9d753015fcac9fc58f1",
                },
            ],
        },
        "resurrection_rule": (
            "recreate_in_atlas_ui_only_with_a_real_production_consumer_"
            "never_restore_in_the_app_tree"
        ),
    }


class UiPrimitivesMixedReceiptTests(unittest.TestCase):
    """Prove aggregate evidence is recomputed instead of trusted by shape."""

    def test_rejects_the_mixed_receipt_on_a_different_ds1_root(self) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        mutation = copy.deepcopy(data)
        primitive_root = next(
            row for row in mutation["entries"] if row["unit_id"] == "ui-primitives-root"
        )
        wrong_root = next(
            row for row in mutation["entries"] if row["unit_id"] == "route-app-layout"
        )
        wrong_root["aggregate_disposition_receipt"] = primitive_root.pop(
            "aggregate_disposition_receipt"
        )

        errors = checker.validate_register(
            mutation,
            live_probes=False,
            report_parity=False,
        )

        self.assertIn("ui_primitives_receipt_wrong_root:route-app-layout", errors)

    def test_live_receipt_is_bound_only_to_ui_primitives_root(self) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        receipt_rows = [
            row["unit_id"] for row in data["entries"] if "aggregate_disposition_receipt" in row
        ]

        self.assertEqual(receipt_rows, ["ui-primitives-root"])

    def test_rejects_retired_count_drift_against_member_decisions(self) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        mutation = copy.deepcopy(data)
        root = next(row for row in mutation["entries"] if row["unit_id"] == "ui-primitives-root")
        root["aggregate_disposition_receipt"] = _mixed_receipt(retired=2)

        errors = checker.validate_register(
            mutation,
            live_probes=False,
            report_parity=False,
        )

        self.assertIn("ui_primitives_receipt_count_drift:retired", errors)

    def test_rejects_a_revived_retired_app_owner(self) -> None:
        errors = checker._ui_primitives_source_state_errors(
            existing_paths={
                *checker.UI_PRIMITIVES_RETAINED_PATHS,
                "apps/runtime-dashboard/src/shared/ui/ApiErrorAlert.tsx",
                "apps/runtime-dashboard/src/shared/ui/ProvenanceStrip.tsx",
                "apps/runtime-dashboard/src/shared/ui/DropdownMenu.tsx",
            },
            dashboard_exports={
                "ApiErrorAlert",
                "DropdownMenu",
                "ProvenanceStrip",
                "ScrollArea",
                "Tabs",
            },
            atlas_exports=set(checker.UI_PRIMITIVES_PACKAGE_MIGRATED),
            production_consumers=[],
        )

        self.assertIn("ui_primitives_retired_owner_revived:DropdownMenu", errors)

    def test_rejects_a_package_only_resurrection(self) -> None:
        errors = checker._ui_primitives_source_state_errors(
            existing_paths={
                *checker.UI_PRIMITIVES_RETAINED_PATHS,
                "apps/runtime-dashboard/src/shared/ui/ApiErrorAlert.tsx",
                "apps/runtime-dashboard/src/shared/ui/ProvenanceStrip.tsx",
                "packages/atlas-ui/src/primitives/Separator.tsx",
            },
            dashboard_exports={
                "ApiErrorAlert",
                "ProvenanceStrip",
                "ScrollArea",
                "Tabs",
            },
            atlas_exports={*checker.UI_PRIMITIVES_PACKAGE_MIGRATED, "Separator"},
            production_consumers=[],
        )

        self.assertIn("ui_primitives_package_counterpart_without_consumer:Separator", errors)

    def test_rejects_valid_looking_resurrection_blob_drift(self) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        mutation = copy.deepcopy(data)
        root = next(row for row in mutation["entries"] if row["unit_id"] == "ui-primitives-root")
        receipt = _mixed_receipt()
        receipt["pre_deletion_resurrection_anchor"]["files"][0]["git_blob"] = "0" * 40
        root["aggregate_disposition_receipt"] = receipt

        errors = checker.validate_register(
            mutation,
            live_probes=False,
            report_parity=False,
        )

        self.assertIn(
            "ui_primitives_anchor_blob_drift:apps/runtime-dashboard/src/shared/ui/DropdownMenu.tsx",
            errors,
        )

    def test_derives_consumers_across_every_required_import_form(self) -> None:
        sources = {
            "apps/runtime-dashboard/src/features/direct.tsx": (
                'import { DropdownMenu } from "@/shared/ui/DropdownMenu";\n'
            ),
            "apps/runtime-dashboard/src/features/barrel.tsx": (
                'import {\n  ScrollArea,\n} from "@/shared/ui";\n'
            ),
            "apps/runtime-dashboard/src/features/namespace.tsx": (
                'import * as UI from "@/shared/ui/primitives";\nconst node = <UI.Sheet />;\n'
            ),
            "apps/runtime-dashboard/src/shared/ui/compounds/relative.tsx": (
                'import { Tabs } from "../Tabs";\n'
            ),
            "apps/runtime-dashboard/src/features/dynamic.tsx": (
                'const module = await import("@/shared/ui/Separator");\n'
            ),
            "apps/runtime-dashboard/src/shared/ui/ScrollArea.tsx": (
                'import { Separator } from "./Separator";\n'
            ),
        }

        observed = checker._ui_primitive_consumers_from_sources(sources)

        self.assertEqual(
            observed,
            [
                "apps/runtime-dashboard/src/features/barrel.tsx:1",
                "apps/runtime-dashboard/src/features/direct.tsx:1",
                "apps/runtime-dashboard/src/features/dynamic.tsx:1",
                "apps/runtime-dashboard/src/features/namespace.tsx:1",
                "apps/runtime-dashboard/src/shared/ui/ScrollArea.tsx:1",
                "apps/runtime-dashboard/src/shared/ui/compounds/relative.tsx:1",
            ],
        )

    def test_ignores_comments_strings_and_type_only_imports(self) -> None:
        sources = {
            "apps/runtime-dashboard/src/features/nonconsumers.ts": (
                '// import { Sheet } from "@/shared/ui";\n'
                "const example = 'import(\"@/shared/ui/Separator\")';\n"
                'import type { Tabs } from "@/shared/ui";\n'
            )
        }

        observed = checker._ui_primitive_consumers_from_sources(sources)

        self.assertEqual(observed, [])

    def test_tracks_reexports_and_precise_dynamic_barrel_members(self) -> None:
        sources = {
            "apps/runtime-dashboard/src/features/reexport.ts": (
                'export { Separator as Divider } from "@/shared/ui";\n'
            ),
            "apps/runtime-dashboard/src/features/namespaceExport.ts": (
                'export * as DormantUi from "@/shared/ui/primitives";\n'
            ),
            "apps/runtime-dashboard/src/features/dynamicDestructure.ts": (
                'const { Tabs } = await import("@/shared/ui");\n'
            ),
            "apps/runtime-dashboard/src/features/dynamicNamespace.ts": (
                'const ui = await import("@/shared/ui/primitives");\nconst node = ui.ScrollArea;\n'
            ),
            "apps/runtime-dashboard/src/features/unrelated.ts": (
                "const Sheet = 'unrelated domain value';\n"
                'const ui = await import("@/shared/ui");\n'
                "const button = ui.Button;\n"
            ),
            "apps/runtime-dashboard/src/features/typeReexport.ts": (
                'export type { Sheet } from "@/shared/ui";\n'
            ),
        }

        observed = checker._ui_primitive_consumers_from_sources(sources)

        self.assertEqual(
            observed,
            [
                "apps/runtime-dashboard/src/features/dynamicDestructure.ts:1",
                "apps/runtime-dashboard/src/features/dynamicNamespace.ts:1",
                "apps/runtime-dashboard/src/features/namespaceExport.ts:1",
                "apps/runtime-dashboard/src/features/reexport.ts:1",
            ],
        )

    def test_tracks_computed_namespace_and_dynamic_promise_access(self) -> None:
        sources = {
            "apps/runtime-dashboard/src/features/computed.tsx": (
                'import * as UI from "@/shared/ui";\nconst node = UI["Tabs"];\n'
            ),
            "apps/runtime-dashboard/src/features/promise.ts": (
                'const promise = import("@/shared/ui").then(({ ScrollArea }) => ScrollArea);\n'
            ),
            "apps/runtime-dashboard/src/features/twoStepPromise.ts": (
                'const uiPromise = import("@/shared/ui");\n'
                "const component = uiPromise.then((ui) => ui.Tabs);\n"
            ),
        }

        observed = checker._ui_primitive_consumers_from_sources(sources)

        self.assertEqual(
            observed,
            [
                "apps/runtime-dashboard/src/features/computed.tsx:1",
                "apps/runtime-dashboard/src/features/promise.ts:1",
                "apps/runtime-dashboard/src/features/twoStepPromise.ts:1",
            ],
        )

    def test_finds_retired_symbols_in_differently_named_owner_modules(self) -> None:
        sources = {
            "apps/runtime-dashboard/src/shared/ui/Overlay.tsx": (
                "const Menu = () => null;\n"
                "export { Menu as DropdownMenu };\n"
                "export function Sheet() { return null; }\n"
            ),
            "packages/atlas-ui/src/primitives/Layout.tsx": (
                "export const Separator = () => null;\n"
            ),
        }

        observed = checker._ui_primitive_owner_refs_from_sources(sources)

        self.assertEqual(
            observed,
            {
                "DropdownMenu": ["apps/runtime-dashboard/src/shared/ui/Overlay.tsx:2"],
                "Separator": ["packages/atlas-ui/src/primitives/Layout.tsx:1"],
                "Sheet": ["apps/runtime-dashboard/src/shared/ui/Overlay.tsx:3"],
            },
        )

    def test_rejects_a_retired_symbol_from_a_differently_named_owner(self) -> None:
        errors = checker._ui_primitives_source_state_errors(
            existing_paths={
                *checker.UI_PRIMITIVES_RETAINED_PATHS,
                "apps/runtime-dashboard/src/shared/ui/ApiErrorAlert.tsx",
                "apps/runtime-dashboard/src/shared/ui/ProvenanceStrip.tsx",
            },
            dashboard_exports={
                "ApiErrorAlert",
                "ProvenanceStrip",
                "ScrollArea",
                "Tabs",
            },
            atlas_exports=set(checker.UI_PRIMITIVES_PACKAGE_MIGRATED),
            production_consumers=[],
            owner_refs={
                "DropdownMenu": ["apps/runtime-dashboard/src/shared/ui/Overlay.tsx:2"],
                "ScrollArea": ["apps/runtime-dashboard/src/shared/ui/ScrollArea.tsx:6"],
                "Tabs": ["apps/runtime-dashboard/src/shared/ui/Tabs.tsx:6"],
            },
        )

        self.assertIn(
            "ui_primitives_retired_symbol_revived:DropdownMenu:"
            "apps/runtime-dashboard/src/shared/ui/Overlay.tsx:2",
            errors,
        )

    def test_requires_a_used_value_import_for_successor_evidence(self) -> None:
        sources = {
            "apps/runtime-dashboard/src/features/comment.ts": (
                '// import { Badge } from "@polisyos/atlas-ui";\n'
            ),
            "apps/runtime-dashboard/src/features/string.ts": (
                'const marker = "@polisyos/atlas-ui";\n'
            ),
            "apps/runtime-dashboard/src/features/type.ts": (
                'import type { Badge } from "@polisyos/atlas-ui";\n'
            ),
            "apps/runtime-dashboard/src/features/unused.ts": (
                'import { Badge } from "@polisyos/atlas-ui";\n'
            ),
            "apps/runtime-dashboard/src/features/shadowed.tsx": (
                'import { Badge } from "@polisyos/atlas-ui";\n'
                "function LocalOnly() {\n"
                "  const Badge = () => null;\n"
                "  return <Badge />;\n"
                "}\n"
            ),
            "apps/runtime-dashboard/src/features/used.tsx": (
                'import { Badge as AtlasBadge } from "@polisyos/atlas-ui";\n'
                "const node = <AtlasBadge />;\n"
            ),
            "apps/runtime-dashboard/src/features/namespace.tsx": (
                'import * as Atlas from "@polisyos/atlas-ui";\nconst node = Atlas["EmptyState"];\n'
            ),
        }

        observed = checker._atlas_ui_value_consumer_refs_from_sources(sources)

        self.assertEqual(
            observed,
            [
                "apps/runtime-dashboard/src/features/namespace.tsx:1",
                "apps/runtime-dashboard/src/features/used.tsx:1",
            ],
        )

    def test_rejects_marker_only_successor_references(self) -> None:
        sources = {
            "apps/runtime-dashboard/src/features/marker.ts": (
                'const marker = "@polisyos/atlas-ui";\n'
            ),
            "apps/runtime-dashboard/src/features/marker.test.ts": (
                '// import { Badge } from "@polisyos/atlas-ui";\n'
            ),
        }

        errors = checker._ui_primitives_successor_evidence_errors(list(sources), sources=sources)

        self.assertEqual(
            errors,
            [
                "ui_primitives_successor_live_consumer_missing",
                "ui_primitives_successor_test_consumer_missing",
            ],
        )


class C15CompoundReceiptTests(unittest.TestCase):
    """Prove migrated compounds retain localized production consumers."""

    def test_rejects_inert_value_mentions_as_live_consumption(self) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        entry = next(
            row for row in data["entries"] if row["unit_id"] == checker.C15_ROOT_ID
        )
        ds2 = json.loads(checker.DS2_PATH.read_text(encoding="utf-8"))
        marker_only_sources = {
            "apps/runtime-dashboard/src/features/marker.tsx": (
                'import { JsonPreview, VirtualList, VirtualTable } '
                'from "@polisyos/atlas-ui";\n'
                "void JsonPreview;\n"
                "const componentMarkers = [VirtualList, VirtualTable];\n"
            ),
            "packages/atlas-ui/src/compounds/owners.tsx": (
                'import { JsonPreview, VirtualList, VirtualTable } '
                'from "@polisyos/atlas-ui";\n'
                "void JsonPreview; void VirtualList; void VirtualTable;\n"
            ),
            "packages/atlas-ui/tests/compoundComponents.test.tsx": (
                'import { JsonPreview, VirtualList, VirtualTable } '
                'from "@polisyos/atlas-ui";\n'
                "void JsonPreview; void VirtualList; void VirtualTable;\n"
            ),
        }
        errors: list[str] = []

        with mock.patch.object(
            checker,
            "_typescript_production_sources",
            return_value=marker_only_sources,
        ):
            checker._validate_c15_mixed_receipt(
                entry,
                ds2,
                errors,
                live_probes=True,
            )

        assert [
            error for error in errors if "production_consumer_missing" in error
        ] == [
            "ui_compounds_root_production_consumer_missing:JsonPreview",
            "ui_compounds_root_production_consumer_missing:VirtualList",
            "ui_compounds_root_production_consumer_missing:VirtualTable",
        ]

    def test_accepts_current_live_jsx_consumers(self) -> None:
        sources = checker._typescript_production_sources(
            ["apps/runtime-dashboard/src"]
        )

        errors = checker._c15_migrated_consumer_errors(sources)

        assert [
            error
            for error in errors
            if "production_consumer_missing" in error
            or "unlocalized_json_preview_consumer" in error
        ] == []

    def test_rejects_raw_json_preview_consumers_outside_the_locale_adapter(self) -> None:
        sources = {
            "apps/runtime-dashboard/src/features/unlocalized.tsx": (
                'import { JsonPreview } from "@polisyos/atlas-ui";\n'
                "const preview = <JsonPreview data={{ status: 'ok' }} />;\n"
            ),
        }

        errors = checker._c15_migrated_consumer_errors(sources)

        assert (
            "ui_compounds_root_unlocalized_json_preview_consumer:"
            "apps/runtime-dashboard/src/features/unlocalized.tsx"
        ) in errors

    def test_rejects_raw_namespace_json_preview_and_counts_namespace_jsx(self) -> None:
        sources = {
            "apps/runtime-dashboard/src/features/unlocalized.tsx": (
                'import * as Atlas from "@polisyos/atlas-ui";\n'
                "const preview = <Atlas.JsonPreview data={{ status: 'ok' }} />;\n"
                "const virtual = <><Atlas.VirtualList /><Atlas.VirtualTable /></>;\n"
            ),
        }

        errors = checker._c15_migrated_consumer_errors(sources)

        assert errors == [
            "ui_compounds_root_unlocalized_json_preview_consumer:"
            "apps/runtime-dashboard/src/features/unlocalized.tsx"
        ]


class C16PatternReceiptTests(unittest.TestCase):
    """Prove the mixed pattern receipt requires real consumers and one owner."""

    def test_rejects_removal_of_either_direct_live_production_import(self) -> None:
        self.assertTrue(
            hasattr(checker, "_c16_pattern_source_state_errors"),
            "C16 checker must recompute pattern ownership and consumption",
        )
        if not hasattr(checker, "_c16_pattern_source_state_errors"):
            return

        sources = {
            "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx": (
                'import { DetailLayout } from "@polisyos/atlas-ui";\n'
                "const layout = <DetailLayout content={null} />;\n"
            ),
            "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx": (
                'import { FilterPanel } from "@polisyos/atlas-ui";\n'
                'const filters = <FilterPanel title="Filters" />;\n'
            ),
        }
        expected_paths = {
            *checker.C16_REQUIRED_PATHS,
        }

        self.assertEqual(
            checker._c16_pattern_source_state_errors(
                sources=sources,
                existing_paths=expected_paths,
                atlas_exports={"DetailLayout", "FilterPanel"},
            ),
            [],
        )
        for removed_path, missing_component in (
            (
                "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx",
                "DetailLayout",
            ),
            (
                "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx",
                "FilterPanel",
            ),
        ):
            reduced_sources = {
                path: text for path, text in sources.items() if path != removed_path
            }

            self.assertIn(
                f"ui_patterns_production_consumer_missing:{missing_component}",
                checker._c16_pattern_source_state_errors(
                    sources=reduced_sources,
                    existing_paths=expected_paths,
                    atlas_exports={"DetailLayout", "FilterPanel"},
                ),
            )

    def test_rejects_searchable_list_promotion_without_production_consumer(self) -> None:
        self.assertTrue(
            hasattr(checker, "_c16_pattern_source_state_errors"),
            "C16 checker must reject speculative SearchableList promotion",
        )
        if not hasattr(checker, "_c16_pattern_source_state_errors"):
            return

        sources = {
            "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx": (
                'import { DetailLayout } from "@polisyos/atlas-ui";\n'
                "const layout = <DetailLayout content={null} />;\n"
            ),
            "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx": (
                'import { FilterPanel } from "@polisyos/atlas-ui";\n'
                'const filters = <FilterPanel title="Filters" />;\n'
            ),
        }
        promoted_paths = {
            *checker.C16_REQUIRED_PATHS,
            "packages/atlas-ui/src/patterns/SearchableList.tsx",
        }

        self.assertIn(
            "ui_patterns_searchable_list_promoted_without_consumer",
            checker._c16_pattern_source_state_errors(
                sources=sources,
                existing_paths=promoted_paths,
                atlas_exports={"DetailLayout", "FilterPanel", "SearchableList"},
            ),
        )


class C17ResponsiveReceiptTests(unittest.TestCase):
    """Prove the responsive receipt stays bounded to generated runtime parity."""

    def test_requires_the_exact_live_use_as_is_receipt(self) -> None:
        self.assertTrue(
            hasattr(checker, "_validate_c17_responsive_receipt"),
            "C17 checker must bind the exact responsive use_as_is receipt",
        )
        if not hasattr(checker, "_validate_c17_responsive_receipt"):
            return

        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        ds2 = checker._load_json(checker.DS2_PATH)
        entry = next(row for row in data["entries"] if row["unit_id"] == "ui-responsive")
        token_entry = next(row for row in data["entries"] if row["unit_id"] == "ui-tokens")
        errors: list[str] = []

        checker._validate_c17_responsive_receipt(
            entry,
            token_entry,
            ds2,
            errors,
            live_probes=True,
        )

        self.assertEqual(errors, [])

    def test_rejects_taxonomy_admission_or_a_false_ds6_evidence_claim(self) -> None:
        self.assertTrue(
            hasattr(checker, "_validate_c17_responsive_receipt"),
            "C17 checker must preserve rejected and DS6-gated evidence boundaries",
        )
        if not hasattr(checker, "_validate_c17_responsive_receipt"):
            return

        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        entry = next(row for row in data["entries"] if row["unit_id"] == "ui-responsive")
        token_entry = next(row for row in data["entries"] if row["unit_id"] == "ui-tokens")
        ds2 = checker._load_json(checker.DS2_PATH)

        taxonomy_admitted = copy.deepcopy(ds2)
        taxonomy = next(
            row
            for row in taxonomy_admitted["entries"]
            if row["id"] == "responsive-breakpoint-taxonomy"
        )
        taxonomy["adoption_verdict"] = "admit_after_refactor"
        taxonomy_errors: list[str] = []
        checker._validate_c17_responsive_receipt(
            entry,
            token_entry,
            taxonomy_admitted,
            taxonomy_errors,
            live_probes=False,
        )
        self.assertIn("ui_responsive_rejected_taxonomy_drift", taxonomy_errors)

        false_ds6_evidence = copy.deepcopy(ds2)
        print_row = next(
            row
            for row in false_ds6_evidence["entries"]
            if row["id"] == "responsive-print-export"
        )
        print_row["authority"]["may_not_use_for"].remove(
            "claiming browser or manual assistive-technology evidence"
        )
        evidence_errors: list[str] = []
        checker._validate_c17_responsive_receipt(
            entry,
            token_entry,
            false_ds6_evidence,
            evidence_errors,
            live_probes=False,
        )
        self.assertIn(
            "ui_responsive_ds6_evidence_boundary_drift:responsive-print-export",
            evidence_errors,
        )


class ProducerBindingDebtTests(unittest.TestCase):
    """Prove producer-binding debt is descriptor-derived and fail closed."""

    finding_id = "run-lifecycle-terminal-fact"
    capability_states = ["producer_missing", "surface_missing"]
    evidence_refs = [
        "packages/runtime-api-client/canonicalRuntimeApiClient.ts:865",
        "packages/runtime-api-client/types.ts:9240",
        "packages/runtime-api-client/types.ts:9258",
        "packages/runtime-api-client/types.ts:9284",
        "src/polisyos/runtime/http/routes/runs.py:179",
        "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:602",
    ]

    @staticmethod
    def _producer_row() -> dict[str, object]:
        return {
            "finding_id": ProducerBindingDebtTests.finding_id,
            "finding_kind": "producer_binding_debt",
            "disposition": "rebind_pending",
            "status": "open_debt",
            "evidence_refs": list(ProducerBindingDebtTests.evidence_refs),
            "owner_slice": "DS3",
            "decision_date": checker.DECISION_DATE,
            "capability_states": list(ProducerBindingDebtTests.capability_states),
            "rationale": (
                "RunSummary exposes open status text and finished_at but no "
                "producer-signed terminal fact; the runtime SSE sibling currently "
                "derives terminality from status substrings, so DS4 must render "
                "labels opaquely and may not mint lifecycle authority."
            ),
            "closure_signal": (
                "DS3 projects a producer-signed terminal/completion fact through "
                "the generated RunSummary and governed event contracts; dashboard "
                "polling, optimistic, Clerk, and run surfaces consume that fact; "
                "novel status labels remain opaque; the C22 semantic negatives and "
                "DS5 ownership lint remain green."
            ),
        }

    @staticmethod
    def _supplemental_schema_messages(row: dict[str, object]) -> list[str]:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        data["supplemental_findings"] = [row]
        return checker._schema_errors(data, checker.SCHEMA_PATH)

    def test_schema_requires_capability_states_and_closure_signal_only_for_producer_binding_debt(
        self,
    ) -> None:
        producer = self._producer_row()
        self.assertEqual([], self._supplemental_schema_messages(producer))

        for field in ("capability_states", "closure_signal"):
            with self.subTest(missing=field):
                mutation = copy.deepcopy(producer)
                mutation.pop(field)
                self.assertTrue(self._supplemental_schema_messages(mutation))

        repaired = copy.deepcopy(producer)
        repaired["repair_commit"] = "a" * 40
        self.assertTrue(self._supplemental_schema_messages(repaired))

        ordinary = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))[
            "supplemental_findings"
        ][0]
        for field, value in (
            ("capability_states", list(self.capability_states)),
            ("closure_signal", producer["closure_signal"]),
        ):
            with self.subTest(forbidden=field):
                mutation = copy.deepcopy(ordinary)
                mutation[field] = value
                self.assertTrue(self._supplemental_schema_messages(mutation))

    def test_capability_state_vocabulary_matches_the_failure_register(self) -> None:
        register_text = (
            checker.REPO_ROOT / "docs/reference/policy-design-case-failure-patterns.md"
        ).read_text(encoding="utf-8")
        expected = [
            "contract_only",
            "producer_missing",
            "artifact_missing",
            "bridge_missing",
            "consumer_missing",
            "verification_missing",
            "implemented_but_not_orchestrated",
            "surface_missing",
            "surface_out_of_scope",
            "semantic_test_missing",
        ]
        observed = [
            line.split("`", 2)[1]
            for line in register_text.splitlines()
            if line.startswith("| `")
        ][: len(expected)]
        schema = json.loads(checker.SCHEMA_PATH.read_text(encoding="utf-8"))
        supplemental = schema["$defs"]["supplementalFinding"]
        schema_states = (
            supplemental.get("properties", {})
            .get("capability_states", {})
            .get("items", {})
            .get("enum", [])
        )

        self.assertEqual(expected, observed)
        self.assertEqual(expected, schema_states)

    def test_producer_binding_debts_are_derived_from_descriptors(self) -> None:
        descriptors = getattr(checker, "PRODUCER_BINDING_DEBT_DESCRIPTORS", {})
        self.assertEqual(
            {
                self.finding_id,
                "authority-issuer-generated-semantic-id-coverage",
                "authority-issuer-parity-operand-binding",
                "producer-binding-readiness-scientific-depth",
                "raw-transport-denominator-drift",
                "capability-discovery-construction-lint-debt",
                "semantic-copy-issuer-panel-consumer-deferral",
            },
            set(descriptors),
        )
        self.assertEqual(
            checker.BASE_EXPECTED_FINDING_IDS
            | set(checker.GOVERNED_DEBT_DESCRIPTORS)
            | set(checker.AUTHORITY_PRESENTATION_DEBT_SPECS),
            checker.EXPECTED_FINDING_IDS,
        )

        generated = {
            row["finding_id"]: row for row in checker._supplemental_findings()
        }
        expected = self._producer_row()
        self.assertEqual(expected, generated[self.finding_id])
        self.assertEqual(
            {key: expected[key] for key in descriptors[self.finding_id]},
            descriptors[self.finding_id],
        )

    def test_readiness_scientific_debt_is_derived_from_one_descriptor(self) -> None:
        finding_id = "producer-binding-readiness-scientific-depth"
        descriptor = checker.PRODUCER_BINDING_DEBT_DESCRIPTORS[finding_id]
        generated = {
            row["finding_id"]: row for row in checker._supplemental_findings()
        }

        self.assertEqual(
            {
                "finding_id": finding_id,
                **descriptor,
                "decision_date": checker.DECISION_DATE,
            },
            generated[finding_id],
        )

    def test_supplemental_refresh_preserves_terminal_history_and_changes_only_the_derived_set(
        self,
    ) -> None:
        original_text = REGISTER_PATH.read_text(encoding="utf-8")
        locate = getattr(checker, "_supplemental_section", None)
        refresh = getattr(checker, "_refresh_supplemental_findings_text", None)
        self.assertTrue(callable(locate) and callable(refresh))
        if not callable(locate) or not callable(refresh):
            return

        original_start, original_end, original_objects = locate(original_text)
        refreshed_text = refresh(original_text)
        refreshed_start, refreshed_end, refreshed_objects = locate(refreshed_text)
        self.assertEqual(refreshed_text, refresh(refreshed_text))
        self.assertEqual(
            original_text[: original_start + 1],
            refreshed_text[: refreshed_start + 1],
        )
        self.assertEqual(original_text[original_end:], refreshed_text[refreshed_end:])
        descriptor_ids = set(checker.GOVERNED_DEBT_DESCRIPTORS)
        self.assertEqual(
            [
                object_text
                for finding_id, object_text in original_objects
                if finding_id not in descriptor_ids
            ],
            [
                object_text
                for finding_id, object_text in refreshed_objects
                if finding_id not in descriptor_ids
            ],
        )
        before = json.loads(original_text)
        refreshed = json.loads(refreshed_text)
        generated_descriptors = {
            row["finding_id"]: row
            for row in checker._supplemental_findings()
            if row["finding_id"] in descriptor_ids
        }
        self.assertEqual(
            generated_descriptors,
            {
                row["finding_id"]: row
                for row in refreshed["supplemental_findings"]
                if row["finding_id"] in descriptor_ids
            },
        )
        for field in sorted(set(before) - {"supplemental_findings"}):
            with self.subTest(field=field):
                self.assertEqual(before[field], refreshed[field])
        self.assertEqual(
            15,
            sum(
                row["disposition"] == "deleted"
                for row in refreshed["entries"]
            ),
        )
        self.assertEqual(
            len(before["reference_censuses"]),
            len(refreshed["reference_censuses"]),
        )

    def test_rejects_run_lifecycle_terminal_debt_drift_in_every_governed_field(
        self,
    ) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        self.assertIn(
            self.finding_id,
            {row["finding_id"] for row in data["supplemental_findings"]},
        )
        mutations = {
            "finding_id": self.finding_id + "-drift",
            "finding_kind": "baseline_test_debt",
            "disposition": "use_as_is",
            "status": "repaired",
            "owner_slice": "DS4",
            "rationale": "drift",
            "capability_states": list(reversed(self.capability_states)),
            "closure_signal": "drift",
            "evidence_refs": list(reversed(self.evidence_refs)),
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                mutation = copy.deepcopy(data)
                row = next(
                    item
                    for item in mutation["supplemental_findings"]
                    if item["finding_id"] == self.finding_id
                )
                row[field] = value
                errors = checker.validate_register(
                    mutation,
                    live_probes=False,
                    report_parity=False,
                )
                self.assertIn(
                    f"producer_binding_debt_drift:{self.finding_id}:{field}",
                    errors,
                )

    def test_rejects_readiness_scientific_debt_drift_in_every_governed_field(
        self,
    ) -> None:
        finding_id = "producer-binding-readiness-scientific-depth"
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        descriptor = checker.PRODUCER_BINDING_DEBT_DESCRIPTORS[finding_id]
        for field, expected in descriptor.items():
            with self.subTest(field=field):
                mutation = copy.deepcopy(data)
                row = next(
                    item
                    for item in mutation["supplemental_findings"]
                    if item["finding_id"] == finding_id
                )
                row[field] = list(reversed(expected)) if isinstance(expected, list) else "drift"
                errors = checker.validate_register(
                    mutation,
                    live_probes=False,
                    report_parity=False,
                )
                self.assertIn(
                    f"producer_binding_debt_drift:{finding_id}:{field}", errors
                )

    def test_report_projects_capability_states_and_closure_signal(self) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        data["supplemental_findings"] = checker._supplemental_findings()
        projection = checker._report_projection(data)
        producer_lines = [
            line for line in projection.splitlines() if f"`{self.finding_id}`" in line
        ]
        self.assertEqual(1, len(producer_lines))
        producer_line = producer_lines[0]
        ordinary_line = next(
            line
            for line in projection.splitlines()
            if "`baseline-test-i18n-count-debt`" in line
        )

        self.assertIn("Capability states", projection)
        self.assertIn("Closure signal", projection)
        self.assertIn("`producer_missing`, `surface_missing`", producer_line)
        self.assertIn(str(self._producer_row()["closure_signal"]), producer_line)
        self.assertIn("| — | — |", ordinary_line)
        readiness_line = next(
            line
            for line in projection.splitlines()
            if "`producer-binding-readiness-scientific-depth`" in line
        )
        self.assertIn("`artifact_missing`", readiness_line)
        self.assertIn("registered typed refusal", readiness_line)


class RawTransportDriftTests(unittest.TestCase):
    """Prove the historical DS1 receipt cannot become a live denominator."""

    def test_raw_transport_drift_row_binds_historical_and_live_census(self) -> None:
        descriptor = checker._raw_transport_drift_descriptor()
        self.assertEqual("raw-transport-denominator-drift", descriptor["finding_id"])
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        row = next(
            item
            for item in data["supplemental_findings"]
            if item["finding_id"] == descriptor["finding_id"]
        )
        self.assertEqual(descriptor, row)

        sources = checker._typescript_production_sources(
            checker.RAW_TRANSPORT_SCAN_ROOTS
        )
        observed = checker._direct_transport_census_from_sources(sources)
        self.assertEqual(
            {
                "fetch_calls": 5,
                "fetch_production_file_count": 3,
                "direct_constructor_count": 7,
                "direct_constructor_production_file_count": 5,
                "kind_counts": {"fetch": 5, "EventSource": 1, "WebSocket": 1},
            },
            {
                "fetch_calls": observed["kind_counts"]["fetch"],
                "fetch_production_file_count": observed["fetch_production_file_count"],
                "direct_constructor_count": observed["direct_constructor_count"],
                "direct_constructor_production_file_count": observed["production_file_count"],
                "kind_counts": observed["kind_counts"],
            },
        )
        census_errors: list[str] = []
        checker._validate_producer_binding_debt_findings(data, census_errors)
        checker._validate_raw_transport_drift(
            data, census_errors, sources=sources
        )
        self.assertEqual([], census_errors)

        for label, mutate in (
            (
                "historical-fetch-denominator",
                lambda receipt: receipt["historical_ds1"].__setitem__(
                    "raw_fetch_calls", 8
                ),
            ),
            (
                "historical-file-denominator",
                lambda receipt: receipt["historical_ds1"].__setitem__(
                    "production_file_count", 4
                ),
            ),
            (
                "live-fetch-denominator",
                lambda receipt: receipt["live_direct_constructor_census"].__setitem__(
                    "fetch_calls", 4
                ),
            ),
            (
                "live-fetch-files",
                lambda receipt: receipt["live_direct_constructor_census"].__setitem__(
                    "fetch_production_file_count", 2
                ),
            ),
            (
                "live-constructor-denominator",
                lambda receipt: receipt["live_direct_constructor_census"].__setitem__(
                    "direct_constructor_count", 6
                ),
            ),
            (
                "live-constructor-files",
                lambda receipt: receipt["live_direct_constructor_census"].__setitem__(
                    "direct_constructor_production_file_count", 4
                ),
            ),
            (
                "live-fetch-kind",
                lambda receipt: receipt["live_direct_constructor_census"][
                    "kind_counts"
                ].__setitem__("fetch", 4),
            ),
            (
                "live-eventsource-kind",
                lambda receipt: receipt["live_direct_constructor_census"][
                    "kind_counts"
                ].__setitem__("EventSource", 0),
            ),
            (
                "live-websocket-kind",
                lambda receipt: receipt["live_direct_constructor_census"][
                    "kind_counts"
                ].__setitem__("WebSocket", 0),
            ),
            (
                "ds19-deletion-evidence",
                lambda receipt: receipt.__setitem__(
                    "ds19_collaboration_deletion_evidence_ref", "docs/missing.md"
                ),
            ),
        ):
            with self.subTest(corruption=label):
                mutation = copy.deepcopy(data)
                target = next(
                    item
                    for item in mutation["supplemental_findings"]
                    if item["finding_id"] == descriptor["finding_id"]
                )
                mutate(target["raw_transport_receipt"])
                errors: list[str] = []
                checker._validate_producer_binding_debt_findings(mutation, errors)
                self.assertIn(
                    "producer_binding_debt_drift:"
                    "raw-transport-denominator-drift:raw_transport_receipt",
                    errors,
                )

        for field, value in (
            ("owner_slice", "DS3"),
            ("capability_states", ["verification_missing"]),
            ("closure_signal", "marker only"),
        ):
            with self.subTest(governed_field=field):
                mutation = copy.deepcopy(data)
                target = next(
                    item
                    for item in mutation["supplemental_findings"]
                    if item["finding_id"] == descriptor["finding_id"]
                )
                target[field] = value
                errors = []
                checker._validate_producer_binding_debt_findings(mutation, errors)
                self.assertIn(
                    "producer_binding_debt_drift:"
                    f"raw-transport-denominator-drift:{field}",
                    errors,
                )

        for field in ("owner_slice", "capability_states", "closure_signal"):
            with self.subTest(omitted_field=field):
                mutation = copy.deepcopy(data)
                target = next(
                    item
                    for item in mutation["supplemental_findings"]
                    if item["finding_id"] == descriptor["finding_id"]
                )
                target.pop(field)
                errors = []
                checker._validate_producer_binding_debt_findings(mutation, errors)
                self.assertTrue(errors)

        benign_sources = {
            **sources,
            "apps/runtime-dashboard/src/shared/lib/directTransportControl.ts": (
                "const control = { fetch: () => undefined };\nvoid control.fetch();\n"
            ),
        }
        self.assertEqual(observed, checker._direct_transport_census_from_sources(benign_sources))
        for label, mutated_sources in (
            (
                "added",
                {
                    **sources,
                    "apps/runtime-dashboard/src/shared/lib/directTransportAdded.ts": (
                        'void fetch("/probe");\n'
                    ),
                },
            ),
            (
                "removed",
                {
                    path: source.replace(
                        "void fetch(TELEMETRY_ENDPOINT, {", "void send(TELEMETRY_ENDPOINT, {"
                    )
                    if path == "apps/runtime-dashboard/src/shared/telemetry/pipeline.ts"
                    else source
                    for path, source in sources.items()
                },
            ),
            (
                "reclassified",
                {
                    path: source.replace("new EventSource(", "new WebSocket(")
                    if path == "apps/runtime-dashboard/src/app/realtime/sseTransport.ts"
                    else source
                    for path, source in sources.items()
                },
            ),
        ):
            with self.subTest(direct_constructor=label):
                errors = []
                checker._validate_raw_transport_drift(
                    data, errors, sources=mutated_sources
                )
                self.assertIn(
                    "raw_transport_live_direct_constructor_census_drift",
                    errors,
                )

        original_text = REGISTER_PATH.read_text(encoding="utf-8")
        with mock.patch.object(
            checker,
            "_supplemental_findings",
            return_value=copy.deepcopy(data["supplemental_findings"]),
        ):
            refreshed_text = checker._refresh_supplemental_findings_text(original_text)
            self.assertEqual(
                refreshed_text,
                checker._refresh_supplemental_findings_text(refreshed_text),
            )
        original_start, original_end, original_rows = checker._supplemental_section(
            original_text
        )
        refreshed_start, refreshed_end, refreshed_rows = checker._supplemental_section(
            refreshed_text
        )
        self.assertEqual(
            original_text[: original_start + 1], refreshed_text[: refreshed_start + 1]
        )
        self.assertEqual(original_text[original_end:], refreshed_text[refreshed_end:])
        generated_ids = set(checker.GOVERNED_DEBT_DESCRIPTORS)
        self.assertEqual(
            [text for finding_id, text in original_rows if finding_id not in generated_ids],
            [text for finding_id, text in refreshed_rows if finding_id not in generated_ids],
        )

    def test_raw_transport_drift_decision_date_is_c03a_specific(self) -> None:
        self.assertEqual(
            "2026-08-08", checker._raw_transport_drift_descriptor()["decision_date"]
        )
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        mutation = copy.deepcopy(data)
        row = next(
            item
            for item in mutation["supplemental_findings"]
            if item["finding_id"] == checker.RAW_TRANSPORT_DRIFT_FINDING_ID
        )
        row["decision_date"] = checker.DECISION_DATE
        self.assertIn(
            "supplemental_decision_date_drift:raw-transport-denominator-drift",
            checker.validate_register(
                mutation, live_probes=False, report_parity=False
            ),
        )

    def test_raw_transport_drift_closure_signal_is_executable_c03b_receipt(self) -> None:
        signal = checker._raw_transport_drift_descriptor()["closure_signal"]
        self.assertIn(
            "test_direct_authority_transport_requires_typed_purpose_factory",
            signal,
        )
        self.assertIn("exits 0", signal)
        self.assertIn("7/5", signal)
        self.assertIn("exit nonzero", signal)
        result = subprocess.run(
            signal,
            shell=True,
            cwd=ATLAS_DIR.parent.parent,
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(3, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        self.assertNotIn("AttributeError", result.stderr)

    def test_raw_transport_debt_closure_requires_lint_and_drift_corruption(self) -> None:
        """Require both named C03b test identities to execute and pass."""

        class OwnerPass(unittest.TestCase):
            def test_direct_authority_transport_requires_typed_purpose_factory(self) -> None:
                self.assertTrue(True)

        class OwnerFail(unittest.TestCase):
            def test_direct_authority_transport_requires_typed_purpose_factory(self) -> None:
                self.fail("owner corruption")

        class DriftPass(unittest.TestCase):
            def test_raw_transport_drift_row_binds_historical_and_live_census(self) -> None:
                self.assertTrue(True)

        class DriftFail(unittest.TestCase):
            def test_raw_transport_drift_row_binds_historical_and_live_census(self) -> None:
                self.fail("drift corruption")

        closure = checker._raw_transport_debt_closure_exit_code
        owner_method = "test_direct_authority_transport_requires_typed_purpose_factory"
        drift_method = "test_raw_transport_drift_row_binds_historical_and_live_census"

        self.assertEqual(3, closure(None, owner_method, DriftPass, drift_method))
        self.assertEqual(3, closure(OwnerPass, "missing_owner_method", DriftPass, drift_method))
        self.assertEqual(4, closure(OwnerPass, owner_method, None, drift_method))
        self.assertEqual(4, closure(OwnerPass, owner_method, DriftPass, "missing_drift_method"))
        self.assertEqual(1, closure(OwnerFail, owner_method, DriftPass, drift_method))
        # A named drift marker without running its failing method must stay red.
        self.assertEqual(1, closure(OwnerPass, owner_method, DriftFail, drift_method))
        self.assertEqual(0, closure(OwnerPass, owner_method, DriftPass, drift_method))

    def test_capability_discovery_lint_debt_closure_requires_declaration_identity_witness(
        self,
    ) -> None:
        """Require both future C04b construction witnesses to execute and pass."""

        class OwnerPass(unittest.TestCase):
            def test_authored_capability_discovery_construction_fails(self) -> None:
                self.assertTrue(True)

            def test_capability_discovery_owner_enclosure_resolves_declaration_identity(
                self,
            ) -> None:
                self.assertTrue(True)

        class ConstructionFail(OwnerPass):
            def test_authored_capability_discovery_construction_fails(self) -> None:
                self.fail("construction corruption")

        class IdentityFail(OwnerPass):
            def test_capability_discovery_owner_enclosure_resolves_declaration_identity(
                self,
            ) -> None:
                self.fail("identity witness skipped")

        closure = checker._capability_discovery_lint_debt_closure_exit_code
        construction_method = "test_authored_capability_discovery_construction_fails"
        identity_method = (
            "test_capability_discovery_owner_enclosure_resolves_declaration_identity"
        )

        self.assertEqual(3, closure(None, construction_method, identity_method))
        self.assertEqual(4, closure(OwnerPass, "missing_construction_method", identity_method))
        self.assertEqual(5, closure(OwnerPass, construction_method, "missing_identity_method"))
        self.assertEqual(1, closure(ConstructionFail, construction_method, identity_method))
        # A named identity marker without running its failing declaration witness stays red.
        self.assertEqual(1, closure(IdentityFail, construction_method, identity_method))
        self.assertEqual(0, closure(OwnerPass, construction_method, identity_method))

    def test_capability_discovery_lint_debt_closure_rejects_non_execution_outcomes(
        self,
    ) -> None:
        """Reject marker-preserving skipped and expected-failure identity witnesses."""

        class OwnerPass(unittest.TestCase):
            def test_authored_capability_discovery_construction_fails(self) -> None:
                self.assertTrue(True)

            def test_capability_discovery_owner_enclosure_resolves_declaration_identity(
                self,
            ) -> None:
                self.assertTrue(True)

        class IdentitySkipped(OwnerPass):
            @unittest.skip("identity witness not executed")
            def test_capability_discovery_owner_enclosure_resolves_declaration_identity(
                self,
            ) -> None:
                self.fail("skipped identity witness")

        class IdentityExpectedFailure(OwnerPass):
            @unittest.expectedFailure
            def test_capability_discovery_owner_enclosure_resolves_declaration_identity(
                self,
            ) -> None:
                self.fail("expected identity failure")

        closure = checker._capability_discovery_lint_debt_closure_exit_code
        construction_method = "test_authored_capability_discovery_construction_fails"
        identity_method = (
            "test_capability_discovery_owner_enclosure_resolves_declaration_identity"
        )

        self.assertEqual(1, closure(IdentitySkipped, construction_method, identity_method))
        self.assertEqual(
            1, closure(IdentityExpectedFailure, construction_method, identity_method)
        )

    def test_raw_transport_receipt_schema_requires_id_and_producer_kind(self) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        row = next(
            item
            for item in data["supplemental_findings"]
            if item["finding_id"] == checker.RAW_TRANSPORT_DRIFT_FINDING_ID
        )
        mutation = copy.deepcopy(row)
        mutation["finding_kind"] = "baseline_test_debt"
        mutation.pop("capability_states")
        mutation.pop("closure_signal")
        self.assertTrue(
            checker._schema_errors(
                {**data, "supplemental_findings": [mutation]}, checker.SCHEMA_PATH
            )
        )

    def test_raw_transport_writer_preservation_oracle_rejects_full_reserialization(self) -> None:
        original = REGISTER_PATH.read_text(encoding="utf-8")
        noncanonical = original.replace('{\n  "$schema"', '{\n\t"$schema"', 1)
        noncanonical = noncanonical.replace(
            '      "finding_id": "baseline-lint-quantity-debt",',
            '\t  "finding_id": "baseline-lint-quantity-debt",',
            1,
        )
        noncanonical = noncanonical.replace(
            '  "seeded_negative_lifecycle": [',
            '  \t"seeded_negative_lifecycle": [',
            1,
        )
        refreshed = checker._refresh_supplemental_findings_text(noncanonical)
        self.assertEqual(
            [],
            checker._raw_transport_writer_preservation_errors(noncanonical, refreshed),
        )
        full_reserialized = json.dumps(
            json.loads(noncanonical), indent=2, ensure_ascii=False
        ) + "\n"
        self.assertTrue(
            checker._raw_transport_writer_preservation_errors(
                noncanonical, full_reserialized
            )
        )
        outside_section_mutant = refreshed.replace(
            '\t"seeded_negative_lifecycle": [',
            '  "seeded_negative_lifecycle": [',
            1,
        )
        self.assertTrue(
            checker._raw_transport_writer_preservation_errors(
                noncanonical, outside_section_mutant
            )
        )


class IntegrateContractDebtTests(unittest.TestCase):
    """Prove the deferred G4 owner contract is typed and corruption-bound."""

    finding_id = "g4-complete-audience-projection-contract"
    integrate_contract: ClassVar[dict[str, object]] = {
        "canonical_projection_id": "policy-design-case-layer3-g4-weakest-boundary",
        "registered_route_posture": "registered_atomically_with_authorization",
        "authorized_audiences": ["EXPERT"],
        "required_permissions": ["mode.analyst"],
        "exact_field_set": [
            "blocker_refs",
            "issue_codes",
            "limitation_refs",
            "produced_by",
            "promotion_scope",
            "promotion_state",
            "status",
            "weakest_boundary_reason",
        ],
        "authoritative_for": [
            "presenting the owner-composed weakest-boundary result and veto "
            "reasons for the current run attempt"
        ],
        "may_not_use_for": [
            "client-side recomposition, averaging, ranking, authorization, "
            "promotion execution, or publication"
        ],
        "provenance_fields": [
            "produced_by.reducer_id",
            "produced_by.reducer_version",
            "produced_by.rule_version",
            "produced_by.vocabulary_status_id",
        ],
        "validator_refs": [
            "tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py"
        ],
        "hash_fields": [
            "produced_by.input_hashes",
            "produced_by.output_hash",
        ],
        "time_semantics": (
            "owner projection supplies an owner as_of or epoch bound to the current "
            "run attempt; filesystem mtime is observation time only"
        ),
        "runtime_novelty_behavior": (
            "novel owner status or projection values fail closed as explicit "
            "unrecognized"
        ),
        "executable_owner_side_closure_signal": (
            "uv run python tools/quality/validation/"
            "check_policy_design_case_layer3_g4_readiness.py --repo-root . "
            "--output-format json exits 0 after owner corruptions prove the "
            "canonical projection ID and exact fields, "
            "public_export_bundle_route_registered=true, an implemented "
            "non-reference-only hook, atomic EXPERT mode.analyst denial, "
            "content hashes, owner time, and runtime novelty behavior"
        ),
    }

    @classmethod
    def _row(cls) -> dict[str, object]:
        return {
            "finding_id": cls.finding_id,
            "finding_kind": "integrate_contract_debt",
            "disposition": "rebind_pending",
            "status": "open_debt",
            "owner_slice": "DS5",
            "owner_team": "team-runtime-quality",
            "capability_states": [
                "implemented_but_not_orchestrated",
                "bridge_missing",
                "consumer_missing",
                "surface_missing",
                "semantic_test_missing",
            ],
            "evidence_refs": [
                "architecture/policy_design_case/layer3_g4_weakest_boundary_composition.json",
                "architecture/policy_design_case/layer3_g4_public_export_projection_refs.json",
                "architecture/policy_design_case/layer3_g4_readiness_manifest.json",
                "architecture/generated_artifacts.toml",
            ],
            "integrate_contract": copy.deepcopy(cls.integrate_contract),
            "rationale": (
                "The G4 owner publishes only reduced reference projections; DS5 may not "
                "invent or route the complete eight-field audience projection."
            ),
            "closure_signal": cls.integrate_contract[
                "executable_owner_side_closure_signal"
            ],
            "decision_date": "2026-08-02",
        }

    def test_schema_requires_external_owner_and_complete_integrate_contract(
        self,
    ) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        data["supplemental_findings"] = [self._row()]
        self.assertEqual([], checker._schema_errors(data, checker.SCHEMA_PATH))

        for field in (
            "owner_team",
            "capability_states",
            "closure_signal",
            "integrate_contract",
        ):
            with self.subTest(missing=field):
                mutation = copy.deepcopy(data)
                mutation["supplemental_findings"][0].pop(field)
                self.assertTrue(checker._schema_errors(mutation, checker.SCHEMA_PATH))

        for field in self.integrate_contract:
            with self.subTest(contract_field=field):
                mutation = copy.deepcopy(data)
                mutation["supplemental_findings"][0]["integrate_contract"].pop(
                    field
                )
                self.assertTrue(checker._schema_errors(mutation, checker.SCHEMA_PATH))

        wrong_owner = copy.deepcopy(data)
        wrong_owner["supplemental_findings"][0]["owner_team"] = "DS5"
        self.assertTrue(checker._schema_errors(wrong_owner, checker.SCHEMA_PATH))

    def test_g4_integrate_debt_is_descriptor_bound_and_corruption_rejected(
        self,
    ) -> None:
        descriptors = checker.INTEGRATE_DEBT_DESCRIPTORS
        self.assertEqual({self.finding_id}, set(descriptors))
        self.assertEqual(
            self._row(), checker.GOVERNED_DEBT_DESCRIPTORS[self.finding_id]
        )

        generated = {
            row["finding_id"]: row for row in checker._supplemental_findings()
        }
        self.assertEqual(self._row(), generated[self.finding_id])

        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        for field in ("owner_team", "capability_states", "integrate_contract"):
            with self.subTest(field=field):
                mutation = copy.deepcopy(data)
                row = next(
                    item
                    for item in mutation["supplemental_findings"]
                    if item["finding_id"] == self.finding_id
                )
                value = row[field]
                row[field] = list(reversed(value)) if isinstance(value, list) else "drift"
                errors = checker.validate_register(
                    mutation,
                    live_probes=False,
                    report_parity=False,
                )
                self.assertIn(
                    f"integrate_contract_debt_drift:{self.finding_id}:{field}",
                    errors,
                )


class AuthorityPresentationCensusTests(unittest.TestCase):
    """Prove every finite C01a sink is branded, benign, or typed debt."""

    def test_every_authority_presentation_prop_is_branded_or_typed_debt(
        self,
    ) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        rows = checker._authority_presentation_rows()

        self.assertEqual(39, len(rows))
        self.assertEqual(
            12,
            sum(row["authority_sink"]["sink_kind"] == "prop_boundary" for row in rows),
        )
        self.assertEqual(
            27,
            sum(
                row["authority_sink"]["sink_kind"] == "direct_badge_group"
                for row in rows
            ),
        )
        self.assertEqual(
            [],
            checker._authority_presentation_errors(data, live_probes=True),
        )

    def test_authority_debt_corruptions_fail_closed(self) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        finding_id = "authority-presentation-prop-control-approval-readiness"
        corruptions = {}

        missing = copy.deepcopy(data)
        missing["supplemental_findings"] = [
            row
            for row in missing["supplemental_findings"]
            if row["finding_id"] != finding_id
        ]
        corruptions["finding_id"] = missing

        for field in ("owner_slice", "capability_states", "closure_signal"):
            mutation = copy.deepcopy(data)
            row = next(
                item
                for item in mutation["supplemental_findings"]
                if item["finding_id"] == finding_id
            )
            row.pop(field)
            corruptions[field] = mutation

        moved = copy.deepcopy(data)
        row = next(
            item
            for item in moved["supplemental_findings"]
            if item["finding_id"] == finding_id
        )
        row["authority_sink"]["consumer_sites"][0]["site_sha256"] = (
            "sha256:" + "0" * 64
        )
        corruptions["authority_sink"] = moved

        for field, mutation in corruptions.items():
            with self.subTest(field=field):
                errors = checker._authority_presentation_errors(
                    mutation, live_probes=False
                )
                self.assertIn(
                    f"authority_presentation_debt_drift:{finding_id}:{field}",
                    errors,
                )

    def test_semantic_copy_deferral_uses_simple_dual_test_closure_signal(self) -> None:
        finding_id = "semantic-copy-issuer-panel-consumer-deferral"
        descriptor = checker.PRODUCER_BINDING_DEBT_DESCRIPTORS[finding_id]
        row = next(
            item
            for item in checker._supplemental_findings()
            if item["finding_id"] == finding_id
        )
        assert row == {
            "finding_id": finding_id,
            **descriptor,
            "decision_date": checker.DECISION_DATE,
        }
        closure = str(descriptor["closure_signal"])
        test_ids = [part for part in closure.split() if ".test_" in part]
        assert len(test_ids) == 2
        assert "python3 -c" not in closure
        assert "helper" not in closure
        assert "exits 0 after both" in closure

    def test_authority_census_rejects_unclassified_and_reclassified_badges(
        self,
    ) -> None:
        scan = checker._authority_presentation_scan()
        classifications = copy.deepcopy(checker.AUTHORITY_BADGE_CLASSIFICATIONS)
        debt_location = next(
            location
            for location, classification in classifications.items()
            if classification.startswith("debt:")
        )
        classifications[debt_location] = "benign:interaction_state"
        errors = checker._badge_classification_errors(scan, classifications)
        self.assertTrue(
            any(error.startswith("authority_badge_reclassification:") for error in errors),
            errors,
        )

        classifications = copy.deepcopy(checker.AUTHORITY_BADGE_CLASSIFICATIONS)
        classifications.pop(next(iter(classifications)))
        errors = checker._badge_classification_errors(scan, classifications)
        self.assertTrue(
            any(error.startswith("authority_badge_unclassified:") for error in errors),
            errors,
        )

        fingerprint_drift = copy.deepcopy(scan)
        benign_location = next(
            location
            for location, classification in checker.AUTHORITY_BADGE_CLASSIFICATIONS.items()
            if classification.startswith("benign:")
        )
        site = next(
            item
            for item in fingerprint_drift["badgeSites"]
            if (item["path"], item["line"]) == benign_location
        )
        site["siteSha256"] = "sha256:" + "0" * 64
        errors = checker._badge_classification_errors(fingerprint_drift)
        self.assertTrue(
            any(
                error.startswith("authority_badge_partition_hash_drift:")
                for error in errors
            ),
            errors,
        )

        prop_fingerprint_drift = copy.deepcopy(scan)
        benign_prop_id = next(
            descriptor_id
            for descriptor_id, spec in checker.AUTHORITY_PROP_CLASSIFICATIONS.items()
            if spec["classification"].startswith("benign:")
        )
        prop_fact = next(
            item
            for item in prop_fingerprint_drift["authorityPropCensus"]
            if item["descriptorId"] == benign_prop_id
        )
        prop_fact["propDeclarationSha256"] = "sha256:" + "0" * 64
        errors = checker._authority_prop_classification_errors(
            prop_fingerprint_drift
        )
        self.assertTrue(
            any(
                error.startswith("authority_prop_partition_hash_drift:")
                for error in errors
            ),
            errors,
        )

    def test_new_direct_badge_site_is_unclassified_until_adjudicated(self) -> None:
        probe_path = (
            "apps/runtime-dashboard/src/shared/lib/domain/"
            "unclassifiedAuthorityBadgeProbe.tsx"
        )
        scan = checker.status_checker._scan(
            {
                probe_path: (
                    'import { Badge } from "@polisyos/atlas-ui";\n'
                    'export const Probe = () => <Badge kind="ok">ready</Badge>;\n'
                )
            },
            authority_prop_descriptors=checker._authority_prop_descriptors(),
        )
        errors = checker._badge_classification_errors(scan)
        self.assertTrue(
            any(
                error.startswith(f"authority_badge_unclassified:{probe_path}:")
                for error in errors
            ),
            errors,
        )

    def test_c01a_dates_and_writer_preserve_accepted_history(self) -> None:
        original_text = REGISTER_PATH.read_text(encoding="utf-8")
        refreshed = checker._refresh_supplemental_findings_text(original_text)
        self.assertEqual(refreshed, checker._refresh_supplemental_findings_text(refreshed))
        before = json.loads(original_text)
        after = json.loads(refreshed)
        new_ids = set(checker.AUTHORITY_PRESENTATION_DEBT_SPECS)

        self.assertEqual(
            {
                row["finding_id"]: row["decision_date"]
                for row in before["supplemental_findings"]
                if row["finding_id"] not in new_ids
            },
            {
                row["finding_id"]: row["decision_date"]
                for row in after["supplemental_findings"]
                if row["finding_id"] not in new_ids
            },
        )
        self.assertEqual(
            {"2026-08-02"},
            {
                row["decision_date"]
                for row in after["supplemental_findings"]
                if row["finding_id"] in new_ids
            },
        )

    def test_duplicate_ids_and_decision_date_rewrites_fail_closed(self) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))

        duplicate = copy.deepcopy(data)
        duplicate["supplemental_findings"].append(
            copy.deepcopy(duplicate["supplemental_findings"][0])
        )
        self.assertIn(
            "duplicate_supplemental_finding_id",
            checker.validate_register(
                duplicate,
                live_probes=False,
                schema=False,
                report_parity=False,
            ),
        )

        old_row = copy.deepcopy(data)
        old_id = old_row["supplemental_findings"][0]["finding_id"]
        old_row["supplemental_findings"][0]["decision_date"] = "2026-08-02"
        self.assertIn(
            f"supplemental_decision_date_drift:{old_id}",
            checker.validate_register(
                old_row,
                live_probes=False,
                schema=False,
                report_parity=False,
            ),
        )

        authority = copy.deepcopy(data)
        authority_row = next(
            row
            for row in authority["supplemental_findings"]
            if row["finding_kind"] == "authority_presentation_debt"
        )
        authority_row["decision_date"] = "2026-07-17"
        self.assertIn(
            "supplemental_decision_date_drift:" + authority_row["finding_id"],
            checker.validate_register(
                authority,
                live_probes=False,
                schema=False,
                report_parity=False,
            ),
        )


if __name__ == "__main__":
    unittest.main()
