"""Focused behavioral tests for the Atlas frontend disposition checker."""

from __future__ import annotations

import base64
import copy
import importlib.util
import json
import re
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
    _c21b_identity_by_hint: ClassVar[dict[str, str] | None] = None
    _c21c_identity_by_hint: ClassVar[dict[str, str] | None] = None

    @classmethod
    def _migrated_descriptor_refs(cls, references: list[str]) -> list[str]:
        """Project legacy fixtures through independently derived identity maps."""
        if cls._c21b_identity_by_hint is None:
            cls._c21b_identity_by_hint = checker._c21b_descriptor_identity_literals()
        if cls._c21c_identity_by_hint is None:
            cls._c21c_identity_by_hint = checker._c21c_structured_identity_literals()
        return [
            cls._c21c_identity_by_hint.get(
                reference,
                cls._c21b_identity_by_hint.get(reference, reference),
            )
            for reference in references
        ]

    @classmethod
    def _producer_row(cls) -> dict[str, object]:
        return {
            "finding_id": cls.finding_id,
            "finding_kind": "producer_binding_debt",
            "disposition": "rebind_pending",
            "status": "open_debt",
            "evidence_refs": cls._migrated_descriptor_refs(cls.evidence_refs),
            "owner_slice": "DS3",
            "decision_date": checker.DECISION_DATE,
            "capability_states": list(cls.capability_states),
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
                "semantic-copy-issuer-panel-consumer-deferral",
                "c06-cgf-public-vocabulary-producer-debt",
                "c06-decision-grade-generated-contract-debt",
                "c06-queryobserver-cache-posture-artifact-debt",
                "c08b-auth-session-revision-producer-debt",
                "c07b-dashboard-generated-client-single-owner-debt",
            },
            set(descriptors),
        )
        self.assertEqual(
            checker.BASE_EXPECTED_FINDING_IDS
            | set(checker.GOVERNED_DEBT_DESCRIPTORS)
            | set(checker.AUTHORITY_PRESENTATION_DEBT_SPECS),
            checker.EXPECTED_FINDING_IDS,
        )

    def test_c07b_dashboard_generated_client_debt_binds_single_owner_strangle(self) -> None:
        """Bind C07b to compiler-resolved imports and the live permission drift."""
        source_root = "apps/runtime-dashboard/src"
        sources = {
            path.relative_to(checker.REPO_ROOT).as_posix(): path.read_text(encoding="utf-8")
            for path in checker._iter_scan_files([source_root])
            if path.suffix in {".ts", ".tsx", ".mts", ".cts"}
        }
        import_facts = [
            fact
            for fact in checker._typescript_module_facts(sources)
            if fact["kind"] == "import_declaration"
        ]
        local_types = (checker.REPO_ROOT / "apps/runtime-dashboard/src/api/types.ts").resolve()
        local_imports = [
            fact
            for fact in import_facts
            if fact["resolved_module"] == "apps/runtime-dashboard/src/api/types.ts"
        ]
        canonical_imports = [
            fact
            for fact in import_facts
            if fact["resolved_module"]
            == "packages/runtime-api-client/canonicalRuntimeApiClient.ts"
        ]
        non_test_local_imports = [
            fact for fact in local_imports if not str(fact["path"]).endswith("validators.test.ts")
        ]
        local_receipts = {
            f"{fact['path']}:{fact['line']}" for fact in local_imports
        }
        non_test_local_receipts = {
            f"{fact['path']}:{fact['line']}" for fact in non_test_local_imports
        }
        self.assertEqual(75, len(canonical_imports))  # noqa: PT009
        self.assertEqual(75, len({fact["path"] for fact in canonical_imports}))  # noqa: PT009
        self.assertEqual(27, len(non_test_local_imports))  # noqa: PT009
        self.assertEqual(27, len({fact["path"] for fact in non_test_local_imports}))  # noqa: PT009
        self.assertEqual(28, len(local_imports))  # noqa: PT009
        self.assertEqual(  # noqa: PT009
            {"apps/runtime-dashboard/src/api/validators.test.ts:4"},
            local_receipts - non_test_local_receipts,
        )
        canonical_source = (checker.REPO_ROOT / "packages/runtime-api-client/types.ts").read_text(
            encoding="utf-8"
        )
        local_source = local_types.read_text(encoding="utf-8")
        self.assertEqual(3, canonical_source.count("RuntimePermission"))  # noqa: PT009
        self.assertEqual(0, local_source.count("RuntimePermission"))  # noqa: PT009
        canonical_permissions = 'permissions?: components["schemas"]["RuntimePermission"][]'
        self.assertIn(canonical_permissions, canonical_source)  # noqa: PT009
        self.assertIn("permissions?: string[]", local_source)  # noqa: PT009

        finding_id = "c07b-dashboard-generated-client-single-owner-debt"
        expected = {
            "finding_kind": "producer_binding_debt",
            "disposition": "rebind_pending",
            "status": "open_debt",
            "owner_slice": "DS5",
            "capability_states": [
                "bridge_missing",
                "consumer_missing",
                "verification_missing",
                "semantic_test_missing",
            ],
            "evidence_refs": [
                "packages/runtime-api-client/types.ts:2430",
                "apps/runtime-dashboard/src/api/types.ts:2323",
                "architecture/generated_artifacts.toml:764",
                "docs/reference/frontend/workspace-contract.md:37",
                "apps/runtime-dashboard/package.json:166",
                "docs/plans/active/atlas-slices/DS5-enforcement-waist.md#ds5-c07b",
            ],
            "rationale": (
                "Canonical package client exists, but the dashboard keeps a divergent local "
                "generated artifact; this row records the single-owner strangle without a "
                "comparator or dashboard change."
            ),
            "closure_signal": (
                "python3 -m unittest architecture.atlas_surfaces."
                "test_frontend_disposition_register.ProducerBindingDebtTests."
                "test_c07b_dashboard_generated_client_has_one_"
                "canonical_owner exits 0 after manifest/reference/package cleanup, deletion of "
                "apps/runtime-dashboard/src/api/types.ts, and all compiler-resolved dashboard "
                "imports directly use @polisyos/runtime-api-client."
            ),
        }
        expected["evidence_refs"] = self._migrated_descriptor_refs(
            expected["evidence_refs"]
        )
        self.assertEqual(  # noqa: PT009
            expected, checker.PRODUCER_BINDING_DEBT_DESCRIPTORS.get(finding_id)
        )
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        rows = {str(row["finding_id"]): row for row in data["supplemental_findings"]}
        self.assertEqual(  # noqa: PT009
            {"finding_id": finding_id, **expected, "decision_date": checker.DECISION_DATE},
            rows.get(finding_id),
        )

    def test_c07b_import_facts_resolve_dashboard_config_aliases(self) -> None:
        """Resolve both dashboard aliases through tsconfig instead of classifying strings."""
        facts = checker._typescript_module_facts(
            {
                "apps/runtime-dashboard/src/features/c07bAliasProbe.ts": (
                    'import type { components } from "@/api/types";\n'
                    'import type { RuntimePermission } from "@polisyos/runtime-api-client";\n'
                )
            }
        )
        imports = [fact for fact in facts if fact["kind"] == "import_declaration"]
        resolved = {fact["module"]: fact.get("resolved_module") for fact in imports}

        self.assertEqual(  # noqa: PT009
            "apps/runtime-dashboard/src/api/types.ts", resolved["@/api/types"]
        )
        self.assertEqual(  # noqa: PT009
            "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
            resolved["@polisyos/runtime-api-client"],
        )

    def test_c14a_local_state_envelope_owner_debt_binds_absent_producer_contract(self) -> None:
        """Close C14a only after the real local-state witness succeeds."""
        finding_id = "c14a-local-state-envelope-owner-debt"
        self.assertNotIn(finding_id, checker.PRODUCER_BINDING_DEBT_DESCRIPTORS)
        refreshed = json.loads(
            checker._refresh_supplemental_findings_text(
                REGISTER_PATH.read_text(encoding="utf-8")
            )
        )
        self.assertNotIn(
            finding_id,
            {str(row["finding_id"]) for row in refreshed["supplemental_findings"]},
        )
        self.assertEqual(
            0,
            subprocess.run(
                [
                    "python3",
                    "-m",
                    "unittest",
                    "architecture.atlas_surfaces.test_atlas_enforcement."
                    "AtlasEnforcementTests."
                    "test_raw_local_state_envelope_cannot_be_issued_or_written",
                ],
                cwd=checker.REPO_ROOT,
                check=False,
            ).returncode,
        )

    def test_capability_discovery_debt_is_closed_when_direct_syntax_rule_is_live(self) -> None:
        """A landed C04b mechanism must remove its deferred producer-binding row."""
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        self.assertNotIn(
            "capability-discovery-construction-lint-debt",
            {row["finding_id"] for row in data["supplemental_findings"]},
        )
        self.assertNotIn(
            "capability-discovery-construction-lint-debt",
            checker.PRODUCER_BINDING_DEBT_DESCRIPTORS,
        )

    def test_c06_waist_owner_debts_bind_three_independent_planes(self) -> None:
        """Keep the three absent C06 producers independently descriptor-bound."""
        expected = {
            "c06-cgf-public-vocabulary-producer-debt": "no public typed owner exists",
            "c06-decision-grade-generated-contract-debt": "C14",
            "c06-queryobserver-cache-posture-artifact-debt": "C11a/C11b",
        }
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        descriptors = checker.PRODUCER_BINDING_DEBT_DESCRIPTORS
        rows = {
            str(row["finding_id"]): row for row in data["supplemental_findings"]
        }
        benign = descriptors["run-lifecycle-terminal-fact"]
        self.assertEqual("DS3", benign["owner_slice"])
        for finding_id, successor in expected.items():
            with self.subTest(finding_id=finding_id):
                descriptor = descriptors[finding_id]
                self.assertIn(successor, str(descriptor["rationale"]))
                self.assertEqual(
                    {
                        "finding_id": finding_id,
                        **descriptor,
                        "decision_date": checker.DECISION_DATE,
                    },
                    rows[finding_id],
                )
                for field, replacement in (
                    ("finding_kind", "baseline_test_debt"),
                    ("owner_slice", "DS4"),
                    ("capability_states", ["surface_missing"]),
                ):
                    mutation = copy.deepcopy(data)
                    target = next(
                        row
                        for row in mutation["supplemental_findings"]
                        if row["finding_id"] == finding_id
                    )
                    target[field] = replacement
                    errors = checker.validate_register(
                        mutation, live_probes=False, report_parity=False
                    )
                    self.assertIn(
                        f"producer_binding_debt_drift:{finding_id}:{field}", errors
                    )
                mutation = copy.deepcopy(data)
                target = next(
                    row
                    for row in mutation["supplemental_findings"]
                    if row["finding_id"] == finding_id
                )
                target.pop("closure_signal")
                errors = checker.validate_register(
                    mutation, live_probes=False, report_parity=False
                )
                self.assertTrue(errors)

        generated = {
            row["finding_id"]: row for row in checker._supplemental_findings()
        }
        expected = self._producer_row()
        self.assertEqual(expected, generated[self.finding_id])
        self.assertEqual(
            {key: expected[key] for key in descriptors[self.finding_id]},
            descriptors[self.finding_id],
        )

    def test_auth_session_revision_debt_binds_generated_auth_me_contract(self) -> None:
        """The missing identity revision stays a producer contract debt."""
        finding_id = "c08b-auth-session-revision-producer-debt"
        expected = {
            "finding_kind": "producer_binding_debt",
            "disposition": "rebind_pending",
            "status": "open_debt",
            "owner_slice": "DS5",
            "capability_states": [
                "producer_missing",
                "artifact_missing",
                "bridge_missing",
                "verification_missing",
                "semantic_test_missing",
            ],
            "evidence_refs": [
                "src/polisyos/runtime/http/routes/auth.py:36",
                "schemas/runtime_api_v1.openapi.json:2221",
                "packages/runtime-api-client/types.ts:2411",
                "apps/runtime-dashboard/src/api/hooks/useAuthMe.ts:42",
                "apps/runtime-dashboard/src/api/queryKeys.ts:11",
            ],
            "rationale": (
                "The runtime HTTP AuthMeResponse, OpenAPI schema, generated client, "
                "useAuthMe, and queryKeys all lack auth_session_revision. This is the "
                "missing client-bound producer contract, not ownership of server identity."
            ),
            "closure_signal": (
                "python3 -m unittest architecture.atlas_surfaces."
                "test_atlas_enforcement.AtlasEnforcementTests."
                "test_auth_me_query_key_partitions_tenant_user_and_revision "
                "tests.unit.runtime.http.test_auth_api.AuthApiTests."
                "test_auth_me_publishes_auth_session_revision "
                "exits 0 after /auth/me and generated AuthMeResponse publish a "
                "server-issued auth_session_revision and queryKeys binds it; "
                "tenant/user-switch corruption fails"
            ),
        }
        expected["evidence_refs"] = self._migrated_descriptor_refs(
            expected["evidence_refs"]
        )

        source_paths = {
            "runtime": "src/polisyos/runtime/http/routes/auth.py",
            "openapi": "schemas/runtime_api_v1.openapi.json",
            "generated": "packages/runtime-api-client/types.ts",
            "hook": "apps/runtime-dashboard/src/api/hooks/useAuthMe.ts",
            "query_key": "apps/runtime-dashboard/src/api/queryKeys.ts",
        }
        sources = {
            source_id: (checker.REPO_ROOT / path).read_text(encoding="utf-8")
            for source_id, path in source_paths.items()
        }

        def brace_block(source: str, declaration: str) -> str:
            declaration_start = source.index(declaration)
            block_start = source.index("{", declaration_start)
            depth = 0
            for index in range(block_start, len(source)):
                if source[index] == "{":
                    depth += 1
                elif source[index] == "}":
                    depth -= 1
                    if depth == 0:
                        return source[block_start : index + 1]
            raise AssertionError(f"unterminated declaration: {declaration}")

        def absence_errors(candidate: dict[str, str]) -> set[str]:
            errors: set[str] = set()
            runtime_match = re.search(
                r"class AuthMeResponse\(BaseModel\):(?P<body>.*?)(?=\n\s*def _sorted_roles)",
                candidate["runtime"],
                re.DOTALL,
            )
            if runtime_match is None:
                errors.add("runtime_auth_me_response_missing")
            elif "auth_session_revision" in runtime_match.group("body"):
                errors.add("runtime_auth_me_revision_present")
            auth_me_route = (
                '@router.get("/me", response_model=AuthMeResponse, operation_id="get_auth_me")'
            )
            if auth_me_route not in candidate["runtime"]:
                errors.add("runtime_auth_me_route_missing")

            openapi = json.loads(candidate["openapi"])
            auth_schema = openapi["components"]["schemas"].get("AuthMeResponse", {})
            if "auth_session_revision" in auth_schema.get("properties", {}):
                errors.add("openapi_auth_me_revision_present")
            if openapi["paths"]["/api/v1/auth/me"]["get"].get("operationId") != "get_auth_me":
                errors.add("openapi_auth_me_operation_missing")

            generated_body = brace_block(candidate["generated"], "AuthMeResponse:")
            if "auth_session_revision" in generated_body:
                errors.add("generated_auth_me_revision_present")

            fetch_body = brace_block(candidate["hook"], "async function fetchAuthMe")
            options_body = brace_block(
                candidate["hook"], "export function authMeQueryOptions"
            )
            if 'buildRuntimeApiUrl("/api/v1/auth/me")' not in fetch_body:
                errors.add("auth_me_hook_route_missing")
            if "authMeSchema.parse(payload)" not in fetch_body:
                errors.add("auth_me_hook_generated_parse_missing")
            if "queryKey: queryKeys.authMe()" not in options_body:
                errors.add("auth_me_hook_query_key_missing")
            if "auth_session_revision" in fetch_body or "auth_session_revision" in options_body:
                errors.add("auth_me_hook_revision_present")

            query_key_match = re.search(
                r"authMe:\s*\(\)\s*=>\s*(?P<key>\[[^\n]+\])\s+as const",
                candidate["query_key"],
            )
            if query_key_match is None:
                errors.add("auth_me_query_key_declaration_missing")
            elif query_key_match.group("key") != '["auth", "me"]':
                errors.add("auth_me_query_key_not_unpartitioned")
            return errors

        self.assertEqual([], sorted(absence_errors(sources)))  # noqa: PT009
        generated_lookalike = dict(sources)
        generated_lookalike["generated"] += (
            '\nexport type SyntheticAuthMeResponse = { auth_session_revision: string };\n'
        )
        self.assertEqual([], sorted(absence_errors(generated_lookalike)))  # noqa: PT009

        openapi_corruption = json.loads(sources["openapi"])
        openapi_corruption["components"]["schemas"]["AuthMeResponse"]["properties"][
            "auth_session_revision"
        ] = {"type": "string"}
        corruptions = {
            "runtime_auth_me_revision_present": {
                **sources,
                "runtime": sources["runtime"].replace(
                    "    meta: ApiMeta", "    auth_session_revision: str\\n    meta: ApiMeta"
                ),
            },
            "openapi_auth_me_revision_present": {
                **sources,
                "openapi": json.dumps(openapi_corruption),
            },
            "generated_auth_me_revision_present": {
                **sources,
                "generated": sources["generated"].replace(
                    "AuthMeResponse: {",
                    "AuthMeResponse: {\\n            auth_session_revision: string;",
                ),
            },
            "auth_me_hook_revision_present": {
                **sources,
                "hook": sources["hook"].replace(
                    "queryKey: queryKeys.authMe(),",
                    "queryKey: queryKeys.authMe(auth_session_revision),",
                ),
            },
            "auth_me_query_key_not_unpartitioned": {
                **sources,
                "query_key": sources["query_key"].replace(
                    'authMe: () => ["auth", "me"] as const,',
                    (
                        'authMe: () => ["auth", "me", '
                        '{ auth_session_revision: "synthetic" }] as const,'
                    ),
                ),
            },
        }
        for expected_error, corruption in corruptions.items():
            with self.subTest(corruption=expected_error):
                self.assertIn(expected_error, absence_errors(corruption))  # noqa: PT009

        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        rows = {item["finding_id"]: item for item in data["supplemental_findings"]}
        self.assertIn(finding_id, rows)  # noqa: PT009
        row = rows[finding_id]
        self.assertEqual(  # noqa: PT009
            {"finding_id": finding_id, **expected, "decision_date": checker.DECISION_DATE}, row
        )
        self.assertEqual(expected, checker.PRODUCER_BINDING_DEBT_DESCRIPTORS[finding_id])  # noqa: PT009

        removed = copy.deepcopy(data)
        removed["supplemental_findings"] = [
            item for item in removed["supplemental_findings"] if item["finding_id"] != finding_id
        ]
        self.assertIn(  # noqa: PT009
            f"producer_binding_debt_drift:{finding_id}:finding_id",
            checker.validate_register(removed, live_probes=False, report_parity=False),
        )

        mutated = copy.deepcopy(data)
        target = next(
            item
            for item in mutated["supplemental_findings"]
            if item["finding_id"] == finding_id
        )
        target["capability_states"] = ["surface_missing"]
        errors = checker.validate_register(mutated, live_probes=False, report_parity=False)
        self.assertIn(  # noqa: PT009
            f"producer_binding_debt_drift:{finding_id}:capability_states", errors
        )
        self.assertEqual(  # noqa: PT009
            {
                "finding_id": "c06-decision-grade-generated-contract-debt",
                **checker.PRODUCER_BINDING_DEBT_DESCRIPTORS[
                    "c06-decision-grade-generated-contract-debt"
                ],
                "decision_date": checker.DECISION_DATE,
            },
            rows["c06-decision-grade-generated-contract-debt"],
        )
        closure_command = expected["closure_signal"].split(" exits 0", 1)[0]
        self.assertNotEqual(  # noqa: PT009
            0,
            subprocess.run(
                closure_command,
                cwd=checker.REPO_ROOT,
                shell=True,
                check=False,
            ).returncode,
        )

    def test_semantic_copy_debt_narrows_after_issuer_lands(self) -> None:
        """An issuer landing clears only the producer half of this debt."""
        descriptor = checker.PRODUCER_BINDING_DEBT_DESCRIPTORS[
            "semantic-copy-issuer-panel-consumer-deferral"
        ]
        self.assertNotIn("producer_missing", descriptor["capability_states"])
        self.assertEqual(
            [
                "bridge_missing",
                "consumer_missing",
                "verification_missing",
                "semantic_test_missing",
            ],
            descriptor["capability_states"],
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
        descriptor_ids = checker._surgical_supplemental_finding_ids(original_text)
        refreshed_descriptor_ids = checker._surgical_supplemental_finding_ids(
            refreshed_text
        )
        self.assertEqual(
            [
                object_text
                for finding_id, object_text in original_objects
                if finding_id not in descriptor_ids
            ],
            [
                object_text
                for finding_id, object_text in refreshed_objects
                if finding_id not in refreshed_descriptor_ids
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
            18,
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
        generated_ids = checker._surgical_supplemental_finding_ids(original_text)
        refreshed_generated_ids = checker._surgical_supplemental_finding_ids(
            refreshed_text
        )
        self.assertEqual(
            [text for finding_id, text in original_rows if finding_id not in generated_ids],
            [
                text
                for finding_id, text in refreshed_rows
                if finding_id not in refreshed_generated_ids
            ],
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

        navigation_only_move = copy.deepcopy(data)
        row = next(
            item
            for item in navigation_only_move["supplemental_findings"]
            if item["finding_id"] == finding_id
        )
        row["authority_sink"]["consumer_sites"][0]["line"] += 1
        self.assertEqual(
            [],
            checker._authority_presentation_errors(
                navigation_only_move, live_probes=False
            ),
        )

        for field, mutation in corruptions.items():
            with self.subTest(field=field):
                errors = checker._authority_presentation_errors(
                    mutation, live_probes=False
                )
                self.assertIn(
                    f"authority_presentation_debt_drift:{finding_id}:{field}",
                    errors,
                )

    def test_semantic_copy_debt_uses_simple_panel_only_closure_signal(self) -> None:
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
        assert len(test_ids) == 1
        assert "python3 -c" not in closure
        assert "helper" not in closure
        assert "RunExplainabilityPanel" in closure
        assert "issuer declaration" not in closure

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

    def test_authority_configuration_keys_are_c21a_identities(self) -> None:
        """Finite Badge/prop classification keys must not encode navigation lines."""
        self.assertTrue(checker.AUTHORITY_BADGE_CLASSIFICATIONS)
        self.assertTrue(checker.AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS)
        for identity in [
            *checker.AUTHORITY_BADGE_CLASSIFICATIONS,
            *checker.AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS,
        ]:
            self.assertRegex(identity, r"^[a-f0-9]{64}$")

    def test_authority_identity_denominators_preserve_shared_prop_declaration(self) -> None:
        """P35: the one shared DecisionCard declaration is multiplicity, not overwrite."""
        scan = checker._authority_presentation_scan()
        badge = checker.AUTHORITY_BADGE_CLASSIFICATIONS
        prop = checker.AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS
        prop_records = [record for records in prop.values() for record in records]
        self.assertEqual(163, len(badge))
        self.assertEqual(163, len(set(badge)))
        self.assertEqual(73, len(prop_records))
        self.assertEqual(72, len(prop))
        shared = [records for records in prop.values() if len(records) == 2]
        self.assertEqual(
            [[
                {"descriptor_id": "prop-decision-card-confidence", "classification": "debt", "role": "component_declaration"},
                {"descriptor_id": "prop-decision-card-verdict", "classification": "debt", "role": "component_declaration"},
            ]],
            [sorted(records, key=lambda record: record["descriptor_id"]) for records in shared],
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
            for location, classification in checker._AUTHORITY_BADGE_CREATION_CLASSIFICATIONS.items()
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
        probe_source = (
            'import { Badge } from "@polisyos/atlas-ui";\n'
            'export const Probe = () => <Badge kind="ok">ready</Badge>;\n'
        )
        scan = checker.status_checker._scan(
            {probe_path: probe_source},
            authority_prop_descriptors=checker._authority_prop_descriptors(),
        )
        target_path = checker.REPO_ROOT / probe_path
        original_read_text = Path.read_text

        def read_text_override(
            path: Path, *args: object, **kwargs: object
        ) -> str:
            if path == target_path:
                return probe_source
            return original_read_text(path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", new=read_text_override):
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
        new_ids = checker._surgical_supplemental_finding_ids(original_text)
        refreshed_new_ids = checker._surgical_supplemental_finding_ids(refreshed)

        self.assertEqual(
            {
                row["finding_id"]: row["decision_date"]
                for row in before["supplemental_findings"]
                if row["finding_id"] not in new_ids
            },
            {
                row["finding_id"]: row["decision_date"]
                for row in after["supplemental_findings"]
                if row["finding_id"] not in refreshed_new_ids
            },
        )
        self.assertEqual(
            {"2026-08-02"},
            {
                row["decision_date"]
                for row in after["supplemental_findings"]
                if row["finding_id"] in checker.AUTHORITY_PRESENTATION_DEBT_SPECS
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


class TypeScriptReferenceIdentityTests(unittest.TestCase):
    """Exercise stable TypeScript reference identities through the real parser."""

    _SOURCE_PATH = "apps/runtime-dashboard/src/features/example/reference.ts"

    def _identity(self, source: str) -> dict[str, str]:
        return checker._typescript_reference_identity(
            {self._SOURCE_PATH: source},
            source_path=self._SOURCE_PATH,
            role="exported_declaration",
            discriminator="publishDecision",
        )

    def test_formatting_and_line_move_preserve_exact_encoded_identity(self) -> None:
        original = """export async function publishDecision(input: string) {
  const label = "decision";
  return `${label}:${input.trim()}`;
}
"""
        moved_and_reformatted = """

// Navigation changed; the declaration did not.
export async function publishDecision( input:string )
{ const label = 'decision'
  return `${label}:${input.trim()}` }
"""

        self.assertEqual(
            self._identity(original)["encoded_identity"],
            self._identity(moved_and_reformatted)["encoded_identity"],
        )

    def test_symbol_rename_emits_named_binding_missing_or_renamed_code(self) -> None:
        reference = self._identity(
            "export async function publishDecision(input: string) { return input; }\n"
        )
        renamed_source = "export async function publishRenamed(input: string) { return input; }\n"

        self.assertIn(
            "typescript_reference_binding_missing_or_renamed",
            checker._validate_typescript_reference_identity(
                reference,
                {self._SOURCE_PATH: renamed_source},
            ),
        )

    def test_construct_rewrite_emits_named_content_drift_code(self) -> None:
        reference = self._identity(
            "export async function publishDecision(input: string) { return input; }\n"
        )
        rewritten_source = (
            "export async function publishDecision(input: string) { return input.toUpperCase(); }\n"
        )

        self.assertIn(
            "typescript_reference_content_drift",
            checker._validate_typescript_reference_identity(
                reference,
                {self._SOURCE_PATH: rewritten_source},
            ),
        )

    def test_import_binding_uses_the_canonical_import_construct(self) -> None:
        source = 'import { components } from "@/api/types";\nexport { components };\n'
        reference = checker._typescript_reference_identity(
            {self._SOURCE_PATH: source},
            source_path=self._SOURCE_PATH,
            role="import_binding",
            discriminator="components",
        )

        self.assertEqual([], checker._validate_typescript_reference_identity(reference, {self._SOURCE_PATH: source}))
        self.assertTrue(
            reference["encoded_identity"].startswith(self._SOURCE_PATH + "#ts-identity=")
        )
        _path, _separator, encoded_payload = reference["encoded_identity"].partition(
            "#ts-identity="
        )
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        )
        self.assertTrue(
            any(
                "apps/runtime-dashboard/src/api/types.ts" in chain_entry
                for chain_entry in payload["declaration_chain"]
            ),
            payload,
        )
        self.assertIn("resolved:components", payload["declaration_chain"])
        self.assertIn(
            "declaration:apps/runtime-dashboard/src/api/types.ts:InterfaceDeclaration",
            payload["declaration_chain"],
        )

    def test_import_binding_fails_closed_when_the_target_export_is_renamed(self) -> None:
        source_path = "apps/runtime-dashboard/src/features/example/reference.ts"
        target_path = "apps/runtime-dashboard/src/features/example/target.ts"
        source = 'import { published } from "./target";\nexport { published };\n'
        reference = checker._typescript_reference_identity(
            {source_path: source, target_path: "export const published = 1;\n"},
            source_path=source_path,
            role="import_binding",
            discriminator="published",
        )

        self.assertIn(
            "typescript_reference_binding_missing_or_renamed",
            checker._validate_typescript_reference_identity(
                reference,
                {source_path: source, target_path: "export const renamed = 1;\n"},
            ),
        )

    def test_jsx_opening_and_attribute_selectors_preserve_role_specific_identity(self) -> None:
        source_path = self._SOURCE_PATH.removesuffix(".ts") + ".tsx"
        source = """export function Surface() {
  return <Badge tone=\"warning\" label=\"Attention\" />;
}
"""
        opening = checker._typescript_reference_identity(
            {source_path: source},
            source_path=source_path,
            role="jsx_opening",
            discriminator="Badge",
        )
        attribute = checker._typescript_reference_identity(
            {source_path: source},
            source_path=source_path,
            role="jsx_attribute",
            discriminator="tone",
        )

        self.assertEqual([], checker._validate_typescript_reference_identity(opening, {source_path: source}))
        self.assertEqual([], checker._validate_typescript_reference_identity(attribute, {source_path: source}))

    def test_jsx_navigation_hint_selects_one_duplicate_without_becoming_the_binding(self) -> None:
        source_path = self._SOURCE_PATH.removesuffix(".ts") + ".tsx"
        source = """export function Surface() {
  return <>
    <Badge tone=\"neutral\" />
    <Badge tone=\"warning\" />
  </>;
}
"""
        reference = checker._typescript_reference_identity(
            {source_path: source},
            source_path=source_path,
            role="jsx_opening",
            discriminator="Badge",
            navigation_hint=4,
        )
        moved = """\nexport function Surface() {
  return <>
    <Badge tone=\"warning\" />
  </>;
}
"""

        self.assertEqual(
            ["typescript_reference_binding_missing_or_renamed"],
            checker._validate_typescript_reference_identity(reference, {source_path: moved}),
        )
        self.assertNotIn("navigation_hint", reference["encoded_identity"])

    def test_duplicate_canonical_candidates_replay_the_structurally_bound_sibling(self) -> None:
        source_path = self._SOURCE_PATH.removesuffix(".ts") + ".tsx"
        one_badge = "export function Surface() { return <Badge tone=\"warning\" />; }\n"
        duplicated_badges = """export function Surface() {
  return <><Badge tone=\"warning\" /><Badge tone=\"warning\" /></>;
}
"""
        reference = checker._typescript_reference_identity(
            {source_path: one_badge},
            source_path=source_path,
            role="jsx_opening",
            discriminator="Badge",
        )

        self.assertEqual(
            ["typescript_reference_binding_missing_or_renamed"],
            checker._validate_typescript_reference_identity(reference, {source_path: duplicated_badges}),
        )


    def test_distinct_content_on_a_second_sibling_does_not_replace_the_bound_sibling(self) -> None:
        source_path = self._SOURCE_PATH.removesuffix(".ts") + ".tsx"
        one_badge = "export function Surface() { return <Badge tone=\"warning\" />; }\n"
        second_distinct_badge = """export function Surface() {
  return <><Badge tone=\"warning\" /><Badge tone=\"neutral\" /></>;
}
"""
        reference = checker._typescript_reference_identity(
            {source_path: one_badge},
            source_path=source_path,
            role="jsx_opening",
            discriminator="Badge",
        )

        self.assertEqual(
            ["typescript_reference_binding_missing_or_renamed"],
            checker._validate_typescript_reference_identity(
                reference,
                {source_path: second_distinct_badge},
            ),
        )

    def test_unknown_identity_payload_version_fails_closed(self) -> None:
        source = "export async function publishDecision(input: string) { return input; }\n"
        reference = self._identity(source)
        source_path, _, encoded_payload = reference["encoded_identity"].partition("#ts-identity=")
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        )
        payload["version"] = 2
        reference["encoded_identity"] = (
            source_path
            + "#ts-identity="
            + base64.urlsafe_b64encode(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).decode("ascii").rstrip("=")
        )

        self.assertEqual(
            ["typescript_reference_identity_invalid"],
            checker._validate_typescript_reference_identity(reference, {self._SOURCE_PATH: source}),
        )

    def test_malformed_or_forged_identity_payload_fails_closed_without_raising(self) -> None:
        source = "export async function publishDecision(input: string) { return input; }\n"
        reference = self._identity(source)
        path_prefix, _separator, encoded_payload = reference["encoded_identity"].partition(
            "#ts-identity="
        )
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        )
        forged_role = dict(payload)
        forged_role["role"] = "forged_role"
        forged_payload = base64.urlsafe_b64encode(
            json.dumps(forged_role, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")

        for encoded_identity in (
            None,
            path_prefix + "#ts-identity=%%%",
            path_prefix + "#ts-identity=" + forged_payload,
        ):
            with self.subTest(encoded_identity=encoded_identity):
                self.assertEqual(
                    ["typescript_reference_identity_invalid"],
                    checker._validate_typescript_reference_identity(
                        {"encoded_identity": encoded_identity},
                        {self._SOURCE_PATH: source},
                    ),
                )

    def test_call_and_string_literal_roles_bind_enclosing_declarations(self) -> None:
        source = """type RunSummary = {
  /** Current governed status. */
  status: string;
};
const routes = { decision: "/api/v1/decisions" };
function publish(summary: RunSummary) {
  return buildSignedPublicDecisionPacket(summary.status);
}
"""
        call_reference = checker._typescript_reference_identity(
            {self._SOURCE_PATH: source},
            source_path=self._SOURCE_PATH,
            role="call_expression",
            discriminator="buildSignedPublicDecisionPacket",
        )
        literal_reference = checker._typescript_reference_identity(
            {self._SOURCE_PATH: source},
            source_path=self._SOURCE_PATH,
            role="string_literal",
            discriminator="/api/v1/decisions",
        )
        type_property_reference = checker._typescript_reference_identity(
            {self._SOURCE_PATH: source},
            source_path=self._SOURCE_PATH,
            role="type_property",
            discriminator="RunSummary.status",
            navigation_hint=2,
        )
        object_property_reference = checker._typescript_reference_identity(
            {self._SOURCE_PATH: source},
            source_path=self._SOURCE_PATH,
            role="object_property",
            discriminator="routes.decision",
        )

        for reference in (
            call_reference,
            literal_reference,
            type_property_reference,
            object_property_reference,
        ):
            self.assertEqual(
                [],
                checker._validate_typescript_reference_identity(reference, {self._SOURCE_PATH: source}),
            )
        self.assertNotIn("navigation_hint", type_property_reference["encoded_identity"])

    def test_c13a_delete_composer_draft_identity_replays_across_line_move(self) -> None:
        """Replay the intended C13a binding across its true line-90 to line-13 move."""
        source_path = "apps/runtime-dashboard/src/app/offline/offlineQueueRepository.ts"
        historical = subprocess.run(
            [
                "git",
                "show",
                "653f12d08^:policy-engine/" + source_path,
            ],
            cwd=checker.REPO_ROOT.parent,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        current = subprocess.run(
            ["git", "show", "653f12d08:policy-engine/" + source_path],
            cwd=checker.REPO_ROOT.parent,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout

        historical_identity = checker._typescript_reference_identity(
            {source_path: historical},
            source_path=source_path,
            role="exported_declaration",
            discriminator="deleteComposerDraftRecord",
        )
        current_identity = checker._typescript_reference_identity(
            {source_path: current},
            source_path=source_path,
            role="exported_declaration",
            discriminator="deleteComposerDraftRecord",
        )
        historical_rendering = json.dumps(
            {"observed_refs": [historical_identity["encoded_identity"]]},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        current_rendering = json.dumps(
            {"observed_refs": [current_identity["encoded_identity"]]},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

        self.assertEqual(historical_identity, current_identity)
        self.assertEqual(historical_rendering, current_rendering)

    def test_c08_content_baselines_remain_whole_file_hashes(self) -> None:
        source = "export async function publishDecision(input: string) { return input; }\n"
        baseline = json.loads(checker.BASELINE_PATH.read_text(encoding="utf-8"))
        c08_binding = next(
            binding
            for binding in baseline["lint"]["resolution_content_bindings"]
            if binding["cluster_id"] == "C08"
        )

        reference = self._identity(source)

        self.assertNotIn("source_content_sha256", reference)
        self.assertIn(
            "lint_resolution_content_hash_drift:C08:" + c08_binding["path"],
            checker._resolution_content_binding_errors(
                baseline["lint"],
                source_bytes_override={c08_binding["path"]: b"C08 whole-file drift"},
            ),
        )

    def test_batch_resolver_builds_multiple_direct_bindings_from_one_snapshot(self) -> None:
        """C21b sends many requests through the C21a batch parser API."""
        source_path = self._SOURCE_PATH
        source = "export const first = 1;\nexport const second = 2;\n"
        facts = checker._typescript_reference_construct_facts_batch(
            {source_path: source},
            [
                {"sourcePath": source_path, "role": "variable_declaration", "discriminator": "first"},
                {"sourcePath": source_path, "role": "variable_declaration", "discriminator": "second"},
            ],
        )
        self.assertEqual(["first", "second"], [row["matches"][0]["discriminator"] for row in facts])
        self.assertEqual([1, 1], [row["programCreateCount"] for row in facts])

    def test_batch_resolver_uses_one_typescript_program_for_many_requests(self) -> None:
        """C21b cannot regress to one compiler process per identity request."""
        source_path = "apps/runtime-dashboard/src/features/example/batch-reference.ts"
        source = "export const first = 1;\nexport const second = 2;\n"
        with mock.patch.object(checker.subprocess, "run", wraps=subprocess.run) as run:
            checker._typescript_reference_construct_facts_batch(
                {source_path: source},
                [
                    {"sourcePath": source_path, "role": "variable_declaration", "discriminator": "first"},
                    {"sourcePath": source_path, "role": "variable_declaration", "discriminator": "second"},
                ],
            )
        self.assertEqual(1, run.call_count)

    def test_type_property_creation_anchor_uses_syntax_start_not_trivia_span(self) -> None:
        """Adjacent inline prop trivia cannot make the line-3 `tone` anchor ambiguous."""
        source_path = self._SOURCE_PATH
        source = """function Atlas({ tone }: {
  title: string;
  tone?: \"accent\" | \"default\";
  trailing?: string;
}) { return tone; }
"""
        facts = checker._typescript_reference_construct_facts_batch(
            {source_path: source},
            [{"sourcePath": source_path, "role": "type_property", "discriminator": "__creation_anchor__"}],
        )[0]
        matches = checker._typescript_reference_anchor_matches(
            facts, {"path": source_path, "line": 3, "role": "type_property"}
        )
        self.assertEqual(["Atlas.tone"], [match["discriminator"] for match in matches])

    def test_type_property_and_jsx_attribute_identities_survive_a_line_move(self) -> None:
        """Authority prop declaration and use gates bind syntax, not navigation."""
        source_path = self._SOURCE_PATH.removesuffix(".ts") + ".tsx"
        original = """type Props = { tone: \"accent\" | \"default\" };
export function Badge({ tone }: Props) { return <span tone={tone} />; }
"""
        moved = """

type Props = { tone: \"accent\" | \"default\" };
export function Badge({ tone }: Props) { return <span tone={tone} />; }
"""
        prop = checker._typescript_reference_identity(
            {source_path: original}, source_path=source_path, role="type_property", discriminator="Props.tone"
        )
        attribute = checker._typescript_reference_identity(
            {source_path: original}, source_path=source_path, role="jsx_attribute", discriminator="tone"
        )
        self.assertEqual([], checker._validate_typescript_reference_identity(prop, {source_path: moved}))
        self.assertEqual([], checker._validate_typescript_reference_identity(attribute, {source_path: moved}))

    def test_protected_call_and_route_literals_replay_without_navigation_lines(self) -> None:
        """The protected-live direct syntax classes survive a move and reject a rewrite."""
        source_path = self._SOURCE_PATH.removesuffix(".ts") + ".tsx"
        original = """function buildSignedPublicDecisionPacket() { return 1; }
const route = \"/public/decisions/:signedId\";
const packet = buildSignedPublicDecisionPacket();
"""
        moved = """
function buildSignedPublicDecisionPacket() { return 1; }
const route = \"/public/decisions/:signedId\";
const packet = buildSignedPublicDecisionPacket();
"""
        call = checker._typescript_reference_identity(
            {source_path: original}, source_path=source_path, role="call_expression", discriminator="buildSignedPublicDecisionPacket"
        )
        route = checker._typescript_reference_identity(
            {source_path: original}, source_path=source_path, role="string_literal", discriminator="/public/decisions/:signedId"
        )
        self.assertEqual([], checker._validate_typescript_reference_identity(call, {source_path: moved}))
        self.assertEqual([], checker._validate_typescript_reference_identity(route, {source_path: moved}))
        self.assertEqual(
            ["typescript_reference_binding_missing_or_renamed"],
            checker._validate_typescript_reference_identity(
                call,
                {source_path: moved.replace("buildSignedPublicDecisionPacket", "renamedPacket")},
            ),
        )
        self.assertEqual(
            ["typescript_reference_binding_missing_or_renamed"],
            checker._validate_typescript_reference_identity(
                route,
                {source_path: moved.replace("public/decisions/:signedId", "public/decisions/:rewritten")},
            ),
        )
        self.assertEqual(
            ["typescript_reference_content_drift"],
            checker._validate_typescript_reference_identity(
                call,
                {source_path: moved.replace("buildSignedPublicDecisionPacket();", "buildSignedPublicDecisionPacket(2);")},
            ),
        )

    def test_same_named_variable_calls_keep_distinct_structural_bindings(self) -> None:
        """Sibling call sites cannot collapse merely because their local name repeats."""
        source_path = self._SOURCE_PATH
        source = """function buildSignedPublicDecisionPacket() { return 1; }
declare function it(name: string, callback: () => void): void;
it("first", () => {
  const signed = buildSignedPublicDecisionPacket();
  return signed;
});
it("second", () => {
  const signed = buildSignedPublicDecisionPacket();
  return signed;
});
"""
        first = checker._typescript_reference_identity(
            {source_path: source}, source_path=source_path, role="call_expression", discriminator="buildSignedPublicDecisionPacket", navigation_hint=4
        )
        second = checker._typescript_reference_identity(
            {source_path: source}, source_path=source_path, role="call_expression", discriminator="buildSignedPublicDecisionPacket", navigation_hint=8
        )
        self.assertNotEqual(first["encoded_identity"], second["encoded_identity"])
        self.assertEqual([], checker._validate_typescript_reference_identity(first, {source_path: source}))
        self.assertEqual([], checker._validate_typescript_reference_identity(second, {source_path: source}))

    def test_real_badge_identity_moves_but_rejects_ambiguity_and_content(self) -> None:
        """A configured Badge binds its enclosing construct rather than its line."""
        location = next(
            location
            for location in sorted(checker._AUTHORITY_BADGE_CREATION_CLASSIFICATIONS)
            if (checker.REPO_ROOT / location[0]).read_text(encoding="utf-8").count(
                "<Badge"
            )
            == 1
        )
        source_path, line = location
        original = (checker.REPO_ROOT / source_path).read_text(encoding="utf-8")
        identity = checker._typescript_reference_identity(
            {source_path: original},
            source_path=source_path,
            role="jsx_opening",
            discriminator="Badge",
            navigation_hint=line,
        )
        digest = checker.hashlib.sha256(
            identity["encoded_identity"].encode("utf-8")
        ).hexdigest()
        self.assertIn(digest, checker.FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS)
        self.assertEqual(
            [],
            checker._validate_typescript_reference_identity(
                identity, {source_path: "\n" + original}
            ),
        )
        rewritten = original.replace(
            "<Badge", '<Badge data-c21b-content="changed"', 1
        )
        self.assertEqual(
            ["typescript_reference_content_drift"],
            checker._validate_typescript_reference_identity(
                identity, {source_path: rewritten}
            ),
        )
        self.assertEqual(
            ["typescript_reference_binding_ambiguous"],
            checker._validate_typescript_reference_identity(
                identity, {source_path: original + "\n" + original}
            ),
        )

    def test_real_prop_declaration_and_use_move_but_reject_rewrite(self) -> None:
        """Configured prop declaration/use identities ignore navigation lines only."""
        descriptor_id = "prop-segmented-control-tone"
        specification = checker.AUTHORITY_PROP_CLASSIFICATIONS[descriptor_id]
        declaration_path = specification["component_declaration_path"]
        declaration_source = (checker.REPO_ROOT / declaration_path).read_text(
            encoding="utf-8"
        )
        declaration = checker._typescript_reference_identity(
            {declaration_path: declaration_source},
            source_path=declaration_path,
            role="type_property",
            discriminator="SegmentedControlProps.tone",
            navigation_hint=specification["prop_declaration_line"],
        )
        declaration_digest = checker.hashlib.sha256(
            declaration["encoded_identity"].encode("utf-8")
        ).hexdigest()
        self.assertIn(
            declaration_digest,
            checker.FROZEN_AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS,
        )
        self.assertEqual(
            [],
            checker._validate_typescript_reference_identity(
                declaration, {declaration_path: "\n" + declaration_source}
            ),
        )
        rewritten = declaration_source.replace(
            'tone?: "default" | "rail";',
            'tone?: "default" | "rail" | "changed";',
            1,
        )
        self.assertEqual(
            ["typescript_reference_content_drift"],
            checker._validate_typescript_reference_identity(
                declaration, {declaration_path: rewritten}
            ),
        )
        renamed = declaration_source.replace("tone?:", "renamedTone?:", 1)
        self.assertEqual(
            ["typescript_reference_binding_missing_or_renamed"],
            checker._validate_typescript_reference_identity(
                declaration, {declaration_path: renamed}
            ),
        )

        use_path, use_line = specification["uses"][0]
        use_source = (checker.REPO_ROOT / use_path).read_text(encoding="utf-8")
        use = checker._typescript_reference_identity(
            {use_path: use_source},
            source_path=use_path,
            role="jsx_attribute",
            discriminator="tone",
            navigation_hint=use_line,
        )
        self.assertEqual(
            [],
            checker._validate_typescript_reference_identity(
                use, {use_path: "\n" + use_source}
            ),
        )


class StructuredReferenceIdentityTests(unittest.TestCase):
    """Exercise JSON/TOML selector identities without binding source addresses."""

    _JSON_PATH = "architecture/example/structured-reference.json"
    _TOML_PATH = "architecture/example/structured-reference.toml"

    def test_json_format_key_order_and_row_move_preserve_identity(self) -> None:
        original = """{
  "entries": [
    {"debt_id": "target", "value": {"alpha": 1, "beta": 2}},
    {"debt_id": "other", "value": {"alpha": 3}}
  ]
}
"""
        moved = """{"entries":[
  {"value":{"alpha":3},"debt_id":"other"},
  {"value":{"beta":2,"alpha":1},"debt_id":"target"}
]}
"""

        first = checker._structured_reference_identity(
            {self._JSON_PATH: original},
            source_path=self._JSON_PATH,
            format_adapter="json",
            selector="/entries[debt_id=target]",
        )
        second = checker._structured_reference_identity(
            {self._JSON_PATH: moved},
            source_path=self._JSON_PATH,
            format_adapter="json",
            selector="/entries[debt_id=target]",
        )

        self.assertEqual(first, second)
        self.assertEqual(
            [],
            checker._validate_structured_reference_identity(
                first, {self._JSON_PATH: moved}
            ),
        )

    def test_toml_format_and_table_move_preserve_identity(self) -> None:
        original = """[[family]]
id = "target"
outputs = ["dist/client.ts"]

[[family]]
id = "other"
outputs = ["dist/other.ts"]
"""
        moved = """[[family]]
outputs=["dist/other.ts"]
id="other"

[[family]]
outputs = [ "dist/client.ts" ]
id = "target"
"""

        first = checker._structured_reference_identity(
            {self._TOML_PATH: original},
            source_path=self._TOML_PATH,
            format_adapter="toml",
            selector="/family[id=target]/outputs",
        )
        second = checker._structured_reference_identity(
            {self._TOML_PATH: moved},
            source_path=self._TOML_PATH,
            format_adapter="toml",
            selector="/family[id=target]/outputs",
        )

        self.assertEqual(first, second)
        self.assertEqual(
            [],
            checker._validate_structured_reference_identity(
                first, {self._TOML_PATH: moved}
            ),
        )

    def test_selector_missing_duplicate_content_drift_and_benign_sibling(self) -> None:
        original = (
            '{"entries":['
            '{"debt_id":"target","value":"kept"},'
            '{"debt_id":"other","value":"control"}'
            "]}"
        )
        reference = checker._structured_reference_identity(
            {self._JSON_PATH: original},
            source_path=self._JSON_PATH,
            format_adapter="json",
            selector="/entries[debt_id=target]",
        )

        cases = {
            "missing": (
                original.replace('"target"', '"renamed"', 1),
                "structured_reference_selector_missing_or_renamed",
            ),
            "duplicate": (
                original.replace(
                    "]}",
                    ',{"debt_id":"target","value":"kept"}]}',
                    1,
                ),
                "structured_reference_selector_ambiguous",
            ),
            "content": (
                original.replace('"kept"', '"rewritten"', 1),
                "structured_reference_content_drift",
            ),
            "non-string-discriminator": (
                original.replace('"target"', "1", 1),
                "structured_reference_selector_missing_or_renamed",
            ),
            "duplicate-object-key": (
                original.replace(
                    '"value":"kept"',
                    '"value":"kept","value":"forged"',
                    1,
                ),
                "structured_reference_source_invalid",
            ),
        }
        for name, (source, code) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(
                    [code],
                    checker._validate_structured_reference_identity(
                        reference, {self._JSON_PATH: source}
                    ),
                )

        benign_sibling_change = original.replace('"control"', '"changed"', 1)
        self.assertEqual(
            [],
            checker._validate_structured_reference_identity(
                reference, {self._JSON_PATH: benign_sibling_change}
            ),
        )

    def test_unsupported_adapter_and_malformed_payload_fail_closed(self) -> None:
        source = '{"target":{"value":1}}\n'
        reference = checker._structured_reference_identity(
            {self._JSON_PATH: source},
            source_path=self._JSON_PATH,
            format_adapter="json",
            selector="/target",
        )
        path, _separator, payload_text = reference["encoded_identity"].partition(
            "#structured-identity="
        )
        payload = json.loads(
            base64.urlsafe_b64decode(payload_text + "=" * (-len(payload_text) % 4))
        )
        payload["format_adapter"] = "yaml"
        def encoded(
            value: dict[str, object], *, prefix: str = path
        ) -> dict[str, str]:
            return {
                "encoded_identity": prefix
                + "#structured-identity="
                + base64.urlsafe_b64encode(
                    json.dumps(
                        value, sort_keys=True, separators=(",", ":")
                    ).encode("utf-8")
                )
                .decode("ascii")
                .rstrip("=")
            }

        unsupported = encoded(payload)

        self.assertEqual(
            ["structured_reference_format_unsupported"],
            checker._validate_structured_reference_identity(
                unsupported, {self._JSON_PATH: source}
            ),
        )

        payload["format_adapter"] = "json"
        version = dict(payload, version=2)
        unknown_key = dict(payload, authorial_line=12)
        path_mismatch = dict(payload, source_path=self._TOML_PATH)
        malformed_cases = (
            encoded(version),
            encoded(unknown_key),
            encoded(payload, prefix=self._TOML_PATH),
        )
        for malformed in malformed_cases:
            with self.subTest(malformed=malformed):
                self.assertEqual(
                    ["structured_reference_identity_invalid"],
                    checker._validate_structured_reference_identity(
                        malformed, {self._JSON_PATH: source}
                    ),
                )
        self.assertEqual(
            ["structured_reference_format_path_mismatch"],
            checker._validate_structured_reference_identity(
                encoded(path_mismatch, prefix=self._TOML_PATH),
                {self._TOML_PATH: source},
            ),
        )
        self.assertEqual(
            ["structured_reference_identity_invalid"],
            checker._validate_structured_reference_identity(
                {"encoded_identity": path + "#structured-identity=%%%"},
                {self._JSON_PATH: source},
            ),
        )

        duplicated_payload = (
            '{"format_adapter":"json","format_adapter":"toml",'
            '"normalized_value_sha256":"'
            + payload["normalized_value_sha256"]
            + '","selector":"/target","source_path":"'
            + self._JSON_PATH
            + '","version":1}'
        )
        self.assertEqual(
            ["structured_reference_identity_invalid"],
            checker._validate_structured_reference_identity(
                {
                    "encoded_identity": path
                    + "#structured-identity="
                    + base64.urlsafe_b64encode(
                        duplicated_payload.encode("utf-8")
                    )
                    .decode("ascii")
                    .rstrip("=")
                },
                {self._JSON_PATH: source},
            ),
        )

        invalid_source_paths = (
            checker.REGISTER_PATH.resolve().as_posix(),
            "architecture/../schemas/runtime_api_v1.openapi.json",
            "architecture//atlas_surfaces/frontend-disposition-register.json",
        )
        for invalid_source_path in invalid_source_paths:
            invalid_payload = dict(payload, source_path=invalid_source_path)
            invalid_reference = encoded(
                invalid_payload,
                prefix=invalid_source_path,
            )
            with self.subTest(invalid_source_path=invalid_source_path):
                self.assertEqual(
                    ["structured_reference_source_path_invalid"],
                    checker._validate_structured_reference_identity(
                        invalid_reference,
                        {invalid_source_path: source},
                    ),
                )
                encoded_identity = invalid_reference["encoded_identity"]
                self.assertEqual(
                    [
                        "structured_reference_source_path_invalid:"
                        + encoded_identity
                    ],
                    checker._structured_identity_reference_errors(
                        [encoded_identity]
                    ),
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "structured_reference_source_path_invalid",
                ):
                    checker._structured_reference_identity(
                        {invalid_source_path: source},
                        source_path=invalid_source_path,
                        format_adapter="json",
                        selector="/target",
                    )

    def test_live_c21c_selector_hashes_are_complete_and_frozen(self) -> None:
        expected_hashes = {
            "architecture/atlas_surfaces/ds4-waist-debt-register.json:16": (
                "d333a5ad21d1303613a7a8a9ca08280afec38ed3437b56511e20c55bd66ab613"
            ),
            "architecture/atlas_surfaces/ds4-waist-debt-register.json:37": (
                "37ae8c9313821507b034e2d085f342b8b2027236d78fcc9258ca50ee4ef69cfe"
            ),
            "architecture/atlas_surfaces/ds4-waist-debt-register.json:57": (
                "a5c57117f529287416ffd2acd55848298955a6c2f13c3ef43f332f2ed1927c4b"
            ),
            "schemas/runtime_api_v1.openapi.json:2221": (
                "7983a50e47d9c0a6e7785de9367614512ce2be27a3e183ac7d844cb4dba6bd3f"
            ),
            "architecture/generated_artifacts.toml:764": (
                "39d976d308c9d0ddd92032f6fafb308091469c06adc631e380e5f08606bc07fa"
            ),
            "apps/runtime-dashboard/package.json:166": (
                "1a900c57304920020c1211fba15c4ad49d05cecc62e94b5e13ca67d9e79c7b56"
            ),
        }

        identities = checker._c21c_structured_identity_literals()
        self.assertEqual(set(expected_hashes), set(identities))
        for legacy_reference, encoded_identity in identities.items():
            _path, payload_text = encoded_identity.split("#structured-identity=", 1)
            payload = json.loads(
                base64.urlsafe_b64decode(
                    payload_text + "=" * (-len(payload_text) % 4)
                )
            )
            self.assertEqual(
                expected_hashes[legacy_reference],
                payload["normalized_value_sha256"],
                legacy_reference,
            )
        descriptor_references = [
            reference
            for descriptor in checker.PRODUCER_BINDING_DEBT_DESCRIPTORS.values()
            for reference in descriptor["evidence_refs"]
            if "#structured-identity=" in reference
        ]
        self.assertEqual(
            set(checker._C21C_FROZEN_STRUCTURED_IDENTITIES.values()),
            set(descriptor_references),
        )
        self.assertEqual(6, len(descriptor_references))


class DS5LineAddressCensusTests(unittest.TestCase):
    """Derive DS5-LINE-ADDRESS-01 denominators from the live register owners."""

    _LINE_REFERENCE_RE = re.compile(r"^(.*?):\d+(?::\d+)?$")
    _BOUNDS_ONLY_REFS = {
        "apps/runtime-dashboard/src/shared/lib/a11yAudit.ts:71",
        "apps/runtime-dashboard/src/shared/i18n/messages/icu-messages.ts:1",
        "apps/runtime-dashboard/src/sw.ts:3",
        "apps/runtime-dashboard/src/sw.ts:4",
        "apps/runtime-dashboard/src/sw.ts:9",
        "apps/runtime-dashboard/src/api/types.ts:7050",
    }

    @classmethod
    def _live_references(cls, data: dict[str, object]) -> list[str]:
        """Walk every observed and evidence reference in the live register."""
        references: list[str] = []
        for census in data["reference_censuses"]:
            for probe in census["probes"]:
                references.extend(probe["observed_refs"])
        for finding in data["supplemental_findings"]:
            references.extend(finding["evidence_refs"])
        return references

    def test_ds5_line_address_complete_partition_is_derived_from_live_register(self) -> None:
        """Make every DS5 line-address denominator fail by its named audit key."""
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        references = self._live_references(data)
        line_references = [reference for reference in references if self._LINE_REFERENCE_RE.match(reference)]
        extension_counts: dict[str, tuple[int, int]] = {}
        for extension in ("TSX", "TS", "PY", "JSON", "MD", "TOML"):
            extension_references = [
                reference
                for reference in line_references
                if Path(self._LINE_REFERENCE_RE.match(reference).group(1)).suffix == "." + extension.lower()
            ]
            extension_counts[extension] = (
                len(extension_references),
                len({self._LINE_REFERENCE_RE.match(reference).group(1) for reference in extension_references}),
            )

        self.assertEqual(264, len(references), "ds5_line_address_total_reference_drift")
        self.assertEqual(15, len(line_references), "ds5_line_address_line_reference_drift")
        self.assertEqual(
            11,
            len({self._LINE_REFERENCE_RE.match(reference).group(1) for reference in line_references}),
            "ds5_line_address_line_file_drift",
        )
        self.assertEqual(
            {"TSX": (0, 0), "TS": (6, 4), "PY": (6, 5), "JSON": (0, 0), "MD": (3, 2), "TOML": (0, 0)},
            extension_counts,
            "ds5_line_address_extension_partition_drift",
        )
        self.assertEqual(
            self._BOUNDS_ONLY_REFS,
            set(line_references) & self._BOUNDS_ONLY_REFS,
            "ds5_line_address_bounds_navigation_drift",
        )
        navigation_references = [
            reference
            for reference in line_references
            if Path(self._LINE_REFERENCE_RE.match(reference).group(1)).suffix
            in {".ts", ".py", ".md"}
        ]
        c21c_structured_references = [
            reference
            for reference in references
            if "#structured-identity=" in reference
        ]
        self.assertEqual(
            15,
            len(navigation_references),
            "ds5_line_address_navigation_reference_drift",
        )
        self.assertEqual(
            6,
            len(c21c_structured_references),
            "ds5_line_address_c21c_structured_reference_drift",
        )
        self.assertEqual(
            4,
            len(
                {
                    reference.split("#structured-identity=", 1)[0]
                    for reference in c21c_structured_references
                }
            ),
            "ds5_line_address_c21c_structured_file_drift",
        )

        observed_line_references = [
            reference
            for census in data["reference_censuses"]
            for probe in census["probes"]
            for reference in probe["observed_refs"]
            if self._LINE_REFERENCE_RE.match(reference)
        ]
        authority_evidence_line_references = [
            reference
            for finding in data["supplemental_findings"]
            if "authority_sink" in finding
            for reference in finding["evidence_refs"]
            if self._LINE_REFERENCE_RE.match(reference)
        ]
        descriptor_evidence_line_references = [
            reference
            for finding in data["supplemental_findings"]
            if "authority_sink" not in finding
            for reference in finding["evidence_refs"]
            if self._LINE_REFERENCE_RE.match(reference)
        ]
        self.assertEqual(0, len(observed_line_references), "ds5_line_address_observed_line_drift")
        self.assertEqual(
            0,
            len(authority_evidence_line_references),
            "ds5_line_address_authority_evidence_line_drift",
        )
        self.assertEqual(
            15,
            len(descriptor_evidence_line_references),
            "ds5_line_address_descriptor_evidence_line_drift",
        )
        identity_references = [reference for reference in references if "#ts-identity=" in reference]
        self.assertEqual(156, len(identity_references), "ds5_c21b_identity_reference_drift")
        identity_payloads = [
            json.loads(
                base64.urlsafe_b64decode(
                    payload + "=" * (-len(payload) % 4)
                )
            )
            for _path, payload in (
                reference.split("#ts-identity=", 1)
                for reference in identity_references
            )
        ]
        self.assertEqual(
            156,
            sum(
                isinstance(payload.get("discriminator"), str)
                and bool(payload["discriminator"])
                for payload in identity_payloads
            ),
            "ds5_c21b_identity_discriminator_drift",
        )
        observed_identities = [
            reference
            for census in data["reference_censuses"]
            for probe in census["probes"]
            for reference in probe["observed_refs"]
            if "#ts-identity=" in reference
        ]
        authority_identities = [
            reference
            for finding in data["supplemental_findings"]
            if "authority_sink" in finding
            for reference in finding["evidence_refs"]
            if "#ts-identity=" in reference
        ]
        descriptor_identities = [
            reference
            for finding in data["supplemental_findings"]
            if "authority_sink" not in finding
            for reference in finding["evidence_refs"]
            if "#ts-identity=" in reference
        ]
        self.assertEqual(28, len(observed_identities), "ds5_c21b_observed_identity_drift")
        self.assertEqual(118, len(authority_identities), "ds5_c21b_authority_identity_drift")
        self.assertEqual(10, len(descriptor_identities), "ds5_c21b_descriptor_identity_drift")
        structured_descriptor_identities = [
            reference
            for finding in data["supplemental_findings"]
            if "authority_sink" not in finding
            for reference in finding["evidence_refs"]
            if "#structured-identity=" in reference
        ]
        self.assertEqual(
            6,
            len(structured_descriptor_identities),
            "ds5_c21c_descriptor_identity_drift",
        )
        self.assertEqual(
            set(checker._C21C_FROZEN_STRUCTURED_IDENTITIES.values()),
            set(structured_descriptor_identities),
            "ds5_c21c_descriptor_identity_set_drift",
        )

        authority_slots = list(checker._AUTHORITY_BADGE_CREATION_CLASSIFICATIONS)
        for specification in checker.AUTHORITY_PROP_CLASSIFICATIONS.values():
            authority_slots.extend(
                [
                    (
                        specification["component_declaration_path"],
                        specification["component_declaration_line"],
                    ),
                    (
                        specification["component_declaration_path"],
                        specification["prop_declaration_line"],
                    ),
                    *specification["uses"],
                ]
            )
        self.assertEqual(236, len(authority_slots), "ds5_line_address_authority_slot_drift")
        self.assertEqual(
            69,
            len({path for path, _line in authority_slots}),
            "ds5_line_address_authority_file_drift",
        )

        authority_rows = [
            finding for finding in data["supplemental_findings"] if "authority_sink" in finding
        ]
        receipt_slots: list[tuple[str, int]] = []
        for row in authority_rows:
            sink = row["authority_sink"]
            receipt_slots.append((sink["component_declaration"]["path"], sink["component_declaration"]["line"]))
            if "prop_declaration" in sink:
                receipt_slots.append((sink["prop_declaration"]["path"], sink["prop_declaration"]["line"]))
            receipt_slots.extend((site["path"], site["line"]) for site in sink["consumer_sites"])
        self.assertEqual(39, len(authority_rows), "ds5_line_address_authority_row_drift")
        self.assertEqual(130, len(receipt_slots), "ds5_line_address_nested_slot_drift")
        self.assertEqual(
            36,
            len({path for path, _line in receipt_slots}),
            "ds5_line_address_nested_file_drift",
        )

    def test_c21b_migrates_every_gated_typescript_reference_to_identity(self) -> None:
        """A line address may navigate TypeScript, but cannot gate its disposition."""
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        references = self._live_references(data)
        legacy_gated_ts = [
            reference
            for reference in references
            if self._LINE_REFERENCE_RE.match(reference)
            and Path(self._LINE_REFERENCE_RE.match(reference).group(1)).suffix in {".ts", ".tsx"}
            and reference not in self._BOUNDS_ONLY_REFS
        ]

        self.assertEqual([], legacy_gated_ts, "ds5_c21b_legacy_gated_typescript_reference")

    def test_c21b_surgical_writer_is_idempotent_on_migrated_register(self) -> None:
        """The surgical writer preserves the complete landed C21b post-state."""
        original = REGISTER_PATH.read_text(encoding="utf-8")
        baseline_before = checker.BASELINE_PATH.read_bytes()
        once = checker._c21b_surgical_identity_text(original)
        twice = checker._c21b_surgical_identity_text(once)
        self.assertEqual(original, once)
        self.assertEqual(once, twice)
        self.assertEqual(baseline_before, checker.BASELINE_PATH.read_bytes())
        migrated = json.loads(once)
        for census in migrated["reference_censuses"]:
            for probe in census["probes"]:
                observed_refs = probe["observed_refs"]
                self.assertEqual(
                    len(observed_refs),
                    len(set(observed_refs)),
                    f"ds5_c21b_observed_identity_duplicate:{census['census_id']}:{probe['kind']}",
                )
        self.assertEqual(
            (28, 118, 10),
            (
                sum(
                    "#ts-identity=" in reference
                    for census in migrated["reference_censuses"]
                    for probe in census["probes"]
                    for reference in probe["observed_refs"]
                ),
                sum(
                    "#ts-identity=" in reference
                    for finding in migrated["supplemental_findings"]
                    if "authority_sink" in finding
                    for reference in finding["evidence_refs"]
                ),
                sum(
                    "#ts-identity=" in reference
                    for finding in migrated["supplemental_findings"]
                    if "authority_sink" not in finding
                    for reference in finding["evidence_refs"]
                ),
            ),
        )
        self.assertEqual(
            6,
            sum(
                reference in self._BOUNDS_ONLY_REFS
                for reference in self._live_references(migrated)
            ),
        )

    def test_c21b_validator_replays_migrated_protected_probe_identities(self) -> None:
        """The live probe consumer compares canonical C21a identities, not navigation lines."""
        migrated = json.loads(
            checker._c21b_surgical_identity_text(REGISTER_PATH.read_text(encoding="utf-8"))
        )
        errors = checker.validate_register(migrated, live_probes=True, report_parity=False)
        probe_suffix = "census-browser-signing-protected-live:reference_count"
        self.assertEqual(
            [],
            [error for error in errors if error.endswith(probe_suffix)],
        )

    def test_c21b_real_gate_ignores_moved_construct_and_rejects_rename(self) -> None:
        """The governed gate binds the migrated construct identity, never its line."""
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        source_path = (
            "apps/runtime-dashboard/src/features/runs/api/"
            "useDepthNCycleBoardProjection.ts"
        )
        stored_references = [
            reference
            for reference in self._live_references(data)
            if reference.startswith(f"{source_path}#ts-identity=")
        ]
        self.assertEqual(1, len(stored_references))
        stored_reference = stored_references[0]

        target_path = checker.REPO_ROOT / source_path
        original = target_path.read_text(encoding="utf-8")
        block = """export function depthNCycleBoardProjectionQueryOptions(
  client: GovernedProjectionClient = governedProjectionClient,
) {
  return {
    queryKey: queryKeys.governedProjection("depth-n-cycle-board"),
    queryFn: async () =>
      narrowDepthNCycleBoardProjection(
        await client.getGovernedProjection({
          projection_id: "depth-n-cycle-board",
        }),
      ),
  };
}
"""
        self.assertEqual(1, original.count(block))
        without_block = original.replace(block, "", 1)
        import_end = without_block.index("\n\n") + 2
        moved = without_block[:import_end] + block + "\n" + without_block[import_end:]
        renamed = moved.replace(
            "depthNCycleBoardProjectionQueryOptions",
            "cycleBoardProjectionQueryOptions",
            1,
        )
        original_read_text = Path.read_text

        def validate_with_source(source: str) -> list[str]:
            def read_text_override(
                path: Path, *args: object, **kwargs: object
            ) -> str:
                if path == target_path:
                    return source
                return original_read_text(path, *args, **kwargs)

            with mock.patch.object(Path, "read_text", new=read_text_override):
                return checker.validate_register(
                    data,
                    live_probes=False,
                    report_parity=False,
                )

        self.assertEqual([], validate_with_source(moved))
        self.assertEqual(
            [
                "typescript_reference_binding_missing_or_renamed:"
                + stored_reference
            ],
            validate_with_source(renamed),
        )

    def test_c21c_surgical_writer_is_idempotent_with_navigation_residual(self) -> None:
        """The governed writer leaves only the 15 declared navigation lines."""
        original = REGISTER_PATH.read_text(encoding="utf-8")
        once = checker._c21c_surgical_identity_text(original)
        twice = checker._c21c_surgical_identity_text(once)
        self.assertEqual(original, once)
        self.assertEqual(once, twice)
        data = json.loads(once)
        references = self._live_references(data)
        structured = [
            reference
            for reference in references
            if "#structured-identity=" in reference
        ]
        remaining_lines = [
            reference
            for reference in references
            if self._LINE_REFERENCE_RE.match(reference)
        ]
        self.assertEqual(
            set(checker._C21C_FROZEN_STRUCTURED_IDENTITIES.values()),
            set(structured),
        )
        self.assertEqual(6, len(structured))
        self.assertEqual(15, len(remaining_lines))

    def test_c21c_real_gate_ignores_json_move_but_rejects_rename_and_content(
        self,
    ) -> None:
        """The full governed validator turns on selector/value identity, not line."""
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        source_path = "architecture/atlas_surfaces/ds4-waist-debt-register.json"
        stored_references = [
            reference
            for reference in self._live_references(data)
            if reference.startswith(f"{source_path}#structured-identity=")
        ]
        self.assertEqual(3, len(stored_references))
        selected_reference = next(
            reference
            for reference in stored_references
            if "ds4-waist-cgf-disposition"
            in json.loads(
                base64.urlsafe_b64decode(
                    reference.split("#structured-identity=", 1)[1]
                    + "="
                    * (
                        -len(reference.split("#structured-identity=", 1)[1])
                        % 4
                    )
                )
            )["selector"]
        )
        target_path = checker.REPO_ROOT / source_path
        original = json.loads(target_path.read_text(encoding="utf-8"))
        moved_data = copy.deepcopy(original)
        moved_data["entries"] = list(reversed(moved_data["entries"]))
        moved = json.dumps(
            moved_data, sort_keys=True, indent=4, ensure_ascii=False
        ) + "\n"
        renamed_data = copy.deepcopy(moved_data)
        renamed_row = next(
            row
            for row in renamed_data["entries"]
            if row["debt_id"] == "ds4-waist-cgf-disposition"
        )
        renamed_row["debt_id"] = "renamed-cgf-disposition"
        renamed = json.dumps(
            renamed_data, sort_keys=True, indent=4, ensure_ascii=False
        ) + "\n"
        changed_data = copy.deepcopy(moved_data)
        changed_row = next(
            row
            for row in changed_data["entries"]
            if row["debt_id"] == "ds4-waist-cgf-disposition"
        )
        changed_row["closure_truth"] += " Rewritten."
        changed = json.dumps(
            changed_data, sort_keys=True, indent=4, ensure_ascii=False
        ) + "\n"
        original_read_text = Path.read_text

        def validate_with_source(source: str) -> list[str]:
            def read_text_override(
                path: Path, *args: object, **kwargs: object
            ) -> str:
                if path == target_path:
                    return source
                return original_read_text(path, *args, **kwargs)

            with mock.patch.object(Path, "read_text", new=read_text_override):
                return checker.validate_register(
                    data, live_probes=False, report_parity=False
                )

        self.assertEqual([], validate_with_source(moved))
        self.assertEqual(
            [
                "structured_reference_selector_missing_or_renamed:"
                + selected_reference
            ],
            [
                error
                for error in validate_with_source(renamed)
                if error.startswith("structured_reference_")
            ],
        )
        self.assertEqual(
            ["structured_reference_content_drift:" + selected_reference],
            [
                error
                for error in validate_with_source(changed)
                if error.startswith("structured_reference_")
            ],
        )


if __name__ == "__main__":
    unittest.main()
