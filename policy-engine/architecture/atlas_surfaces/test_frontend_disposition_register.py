"""Focused behavioral tests for the Atlas frontend disposition checker."""

from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import unittest
from collections import Counter
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


class PersistenceConstructionCensusTests(unittest.TestCase):
    """Prove explicit storage adjudications cannot self-attest or drift class."""

    def test_storage_construction_rows_validate_explicit_adjudication(self) -> None:
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))

        def errors_for(mutation: dict[str, object]) -> list[str]:
            errors: list[str] = []
            checker._validate_storage_construction_census(mutation, errors)
            return errors

        self.assertEqual([], errors_for(data))
        self.assertEqual(
            "institutionally_supplied",
            data["storage_construction_census"]["semantic_class_provenance"],
        )
        sites = data["storage_construction_census"]["sites"]

        corruptions: dict[str, tuple[dict[str, object], str]] = {}

        duplicate = copy.deepcopy(data)
        duplicate_sites = duplicate["storage_construction_census"]["sites"]
        duplicate_sites[1]["site_id"] = duplicate_sites[0]["site_id"]
        corruptions["duplicate"] = (
            duplicate,
            "storage_construction_duplicate_site_id:",
        )

        fingerprint = copy.deepcopy(data)
        fingerprint["storage_construction_census"]["sites"][0][
            "source_fingerprint"
        ] = "sha256:" + "0" * 64
        corruptions["source-fingerprint"] = (
            fingerprint,
            "storage_construction_source_fingerprint_drift:",
        )

        retagged = copy.deepcopy(data)
        scoped = next(
            row
            for row in retagged["storage_construction_census"]["sites"]
            if row["classification"] == "scoped_authority"
        )
        scoped["classification"] = "interaction_benign"
        scoped["benign_reason"] = "ui_preference"
        scoped.pop("scoped_envelope_owner")
        scoped.pop("registered_codec_id")
        corruptions["class"] = (
            retagged,
            "storage_construction_class_distribution_drift",
        )

        wrong_owner = copy.deepcopy(data)
        governed = next(
            row
            for row in wrong_owner["storage_construction_census"]["sites"]
            if row["classification"] == "scoped_authority"
            and row["path"] != row["scoped_envelope_owner"]
        )
        governed["scoped_envelope_owner"] = governed["path"]
        corruptions["owner"] = (
            wrong_owner,
            "storage_construction_scoped_owner_drift:",
        )

        factory_source = copy.deepcopy(data)
        factory_source["storage_construction_census"][
            "authority_factory_receipts"
        ][0]["source_fingerprint"] = "sha256:" + "0" * 64
        corruptions["factory-source"] = (
            factory_source,
            "storage_construction_factory_source_fingerprint_drift:",
        )

        retired_binding = copy.deepcopy(data)
        governed = next(
            row
            for row in retired_binding["storage_construction_census"]["sites"]
            if row["classification"] == "scoped_authority"
        )
        governed["authority_binding"] = {"proof_kind": "self_attested"}
        corruptions["retired-binding"] = (
            retired_binding,
            "storage_construction_retired_authority_binding:",
        )

        for field in checker.C17B_AUTHORITY_FLOW_LIMITATION:
            limitation = copy.deepcopy(data)
            limitation["storage_construction_census"][field] = "false-claim"
            corruptions[f"limitation-{field}"] = (
                limitation,
                f"storage_construction_authority_flow_limit_drift:{field}",
            )

        operation = copy.deepcopy(data)
        operation["storage_construction_census"]["sites"][0]["operation"] = "clear"
        corruptions["operation-digest"] = (
            operation,
            "storage_construction_rows_digest_drift",
        )

        resolved_api = copy.deepcopy(data)
        resolved_api["storage_construction_census"]["sites"][0][
            "resolved_api_declaration"
        ] = "typescript/lib/lib.dom.d.ts::Storage.clear"
        corruptions["resolved-api-digest"] = (
            resolved_api,
            "storage_construction_rows_digest_drift",
        )

        site_fingerprint = copy.deepcopy(data)
        site_fingerprint["storage_construction_census"]["sites"][0][
            "site_fingerprint"
        ] = "sha256:" + "0" * 64
        corruptions["site-fingerprint-digest"] = (
            site_fingerprint,
            "storage_construction_rows_digest_drift",
        )

        benign_debt = copy.deepcopy(data)
        benign = next(
            row
            for row in benign_debt["storage_construction_census"]["sites"]
            if row["classification"] == "interaction_benign"
        )
        benign["owner_slice"] = "DS5"
        corruptions["benign-debt"] = (
            benign_debt,
            "storage_construction_benign_debt_field:",
        )

        benign_reason = copy.deepcopy(data)
        benign = next(
            row
            for row in benign_reason["storage_construction_census"]["sites"]
            if row["classification"] == "interaction_benign"
        )
        benign["benign_reason"] = "theme"
        corruptions["benign-reason"] = (
            benign_reason,
            "storage_construction_benign_owner_drift:",
        )

        missing_path = copy.deepcopy(data)
        missing_path["storage_construction_census"]["sites"][0]["store_owner"] = (
            "apps/runtime-dashboard/src/missing-storage-owner.ts"
        )
        corruptions["missing-owner-path"] = (
            missing_path,
            "storage_construction_store_owner_missing:",
        )

        self.assertEqual(36, len(sites))
        self.assertEqual(
            {"interaction_benign": 22, "scoped_authority": 14},
            dict(Counter(row["classification"] for row in sites)),
        )
        flag_rows = [
            row
            for row in sites
            if row["path"] == "apps/runtime-dashboard/src/shared/lib/featureFlags.ts"
        ]
        self.assertEqual(4, len(flag_rows))
        self.assertTrue(
            all(
                row["classification"] == "interaction_benign"
                and row["benign_reason"] == "rollout_exposure_control"
                for row in flag_rows
            ),
            flag_rows,
        )
        self.assertEqual(10, len(data["reference_censuses"]))
        self.assertEqual(
            {
                "deleted": 19,
                "rebind_pending": 184,
                "retire_disposition": 25,
                "use_as_is": 17,
                "wire_disposition": 16,
            },
            dict(Counter(row["disposition"] for row in data["entries"])),
        )
        self.assertEqual(
            {"not_applicable": 58, "pending": 149, "strangled": 54},
            dict(Counter(row["strangle_status"] for row in data["entries"])),
        )
        projection = checker._report_projection(data)
        self.assertIn("### Persistence construction census", projection)
        self.assertIn("authority flow `not_established`", projection)
        self.assertIn("Declared bounded residual:", projection)
        self.assertEqual(36, projection.count("| `storage-site-"))
        self.assertEqual(
            data["storage_construction_census"],
            checker.build_seed_register()["storage_construction_census"],
        )
        entries = {row["unit_id"]: row for row in data["entries"]}
        self.assertEqual(
            ("use_as_is", "not_applicable"),
            (
                entries["cache-local-storage-state"]["disposition"],
                entries["cache-local-storage-state"]["strangle_status"],
            ),
        )
        self.assertEqual(
            ("deleted", "strangled", "census-review-attention-delete"),
            (
                entries["cache-review-attention"]["disposition"],
                entries["cache-review-attention"]["strangle_status"],
                entries["cache-review-attention"]["reference_census_id"],
            ),
        )
        for label, (mutation, expected_prefix) in corruptions.items():
            with self.subTest(corruption=label):
                self.assertTrue(
                    any(
                        error == expected_prefix or error.startswith(expected_prefix)
                        for error in errors_for(mutation)
                    ),
                    errors_for(mutation),
                )

    def test_review_attention_import_census_covers_static_barrel_and_dynamic(self) -> None:
        target = (
            "apps/runtime-dashboard/src/features/runs/domain/"
            "publicSectorReadiness.ts"
        )
        sources = {
            "apps/runtime-dashboard/src/features/probe/direct.ts": (
                'import * as readiness from "@/features/runs/domain/'
                'publicSectorReadiness";\nvoid readiness;\n'
            ),
            "apps/runtime-dashboard/src/features/probe/barrel.ts": (
                'export * from "../runs/domain/publicSectorReadiness";\n'
            ),
            "apps/runtime-dashboard/src/features/probe/dynamic.ts": (
                'void import("../runs/domain/publicSectorReadiness");\n'
            ),
            "apps/runtime-dashboard/src/features/probe/composed.ts": (
                'void import("../runs/domain/publicSectorReadiness")'
                '.then((module) => module);\n'
            ),
            "apps/runtime-dashboard/src/features/probe/unrelated.ts": (
                'import "@/features/other/publicSectorReadiness";\n'
            ),
            "apps/runtime-dashboard/src/features/probe/unrelated-relative.ts": (
                'export * from "../other/publicSectorReadiness";\n'
            ),
            "apps/runtime-dashboard/src/features/probe/unrelated-suffix.ts": (
                'import "@/features/runs/domain/sub/publicSectorReadiness";\n'
            ),
        }
        self.assertEqual(
            [
                "apps/runtime-dashboard/src/features/probe/barrel.ts:1",
                "apps/runtime-dashboard/src/features/probe/composed.ts:1",
                "apps/runtime-dashboard/src/features/probe/direct.ts:1",
                "apps/runtime-dashboard/src/features/probe/dynamic.ts:1",
            ],
            checker._typescript_import_matches([target], [], sources=sources),
        )
        self.assertEqual(
            [],
            checker._typescript_import_matches(
                [target],
                [
                    "apps/runtime-dashboard/src",
                    "apps/runtime-dashboard/e2e",
                    "apps/runtime-dashboard/.storybook",
                    "apps/runtime-dashboard/scripts",
                    "packages",
                ],
            ),
        )

        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        injected_path = checker.REPO_ROOT / (
            "apps/runtime-dashboard/src/shared/lib/featureFlags.ts"
        )
        original_read_text = Path.read_text

        def read_with_resurrection(path: Path, *args: object, **kwargs: object) -> str:
            text = original_read_text(path, *args, **kwargs)
            if path == injected_path:
                return (
                    'import "@/features/runs/domain/publicSectorReadiness";\n'
                    + text
                )
            return text

        with mock.patch.object(Path, "read_text", autospec=True, side_effect=read_with_resurrection):
            errors = checker.validate_register(
                data,
                live_probes=True,
                report_parity=False,
            )
        self.assertTrue(
            any(
                error.startswith(
                    "census_observation_drift:census-review-attention-delete:"
                    "typescript_import_census"
                )
                for error in errors
            ),
            errors,
        )


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
    capability_states = [
        "consumer_missing",
        "surface_missing",
        "semantic_test_missing",
    ]
    evidence_refs = [
        "packages/runtime-api-client/canonicalRuntimeApiClient.ts:865",
        "packages/runtime-api-client/types.ts:9240",
        "packages/runtime-api-client/types.ts:9258",
        "packages/runtime-api-client/types.ts:9284",
        "src/polisyos/runtime/http/services/adapters/core_run.py",
        "docs/superpowers/journals/2026-08-16-gy-gap4-run-terminality.md",
        "docs/superpowers/specs/2026-08-20-ds7-cycle-board-design.md",
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
            "owner_slice": "DS7",
            "decision_date": checker.DECISION_DATE,
            "capability_states": list(cls.capability_states),
            "rationale": (
                "GAP4 now supplies producer-owned lifecycle terminality through "
                "RunSummary and both generated clients. The DS7 hero consumer and "
                "its absence/proxy semantic tests have not landed yet."
            ),
            "closure_signal": (
                "DS7 renders the producer-signed RunSummary.run_terminality value "
                "without status/timestamp derivation, renders an unbound lifecycle "
                "fact as absent rather than false, and keeps the C22 semantic "
                "negatives plus DS5 ownership lint green."
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
        self.assertEqual(3, local_source.count("RuntimePermission"))  # noqa: PT009
        canonical_permissions = 'permissions?: components["schemas"]["RuntimePermission"][]'
        self.assertIn(canonical_permissions, canonical_source)  # noqa: PT009
        self.assertIn(canonical_permissions, local_source)  # noqa: PT009

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
                    sys.executable,
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

    def test_c06_waist_owner_debts_bind_remaining_independent_planes(self) -> None:
        """Keep only the C06 producer planes whose owners remain absent."""
        expected = {
            "c06-cgf-public-vocabulary-producer-debt": "no public typed owner exists",
            "c06-decision-grade-generated-contract-debt": "C14",
        }
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        descriptors = checker.PRODUCER_BINDING_DEBT_DESCRIPTORS
        rows = {
            str(row["finding_id"]): row for row in data["supplemental_findings"]
        }
        benign = descriptors["run-lifecycle-terminal-fact"]
        self.assertEqual("DS7", benign["owner_slice"])
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

    def test_c11b_cache_posture_debt_closes_after_typed_consumer(self) -> None:
        """Retire the C06 debt once C11a/C11b issue and render cache posture."""
        finding_id = "c06-queryobserver-cache-posture-artifact-debt"
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

    def test_c11b_query_memory_root_binds_exact_bounded_successor(self) -> None:
        """Reject a generic root flip that omits the owner, debt, or live consumer."""
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        entry = next(
            row
            for row in data["entries"]
            if row["unit_id"] == checker.C11B_QUERY_MEMORY_ROOT_ID
        )
        baseline_errors: list[str] = []
        checker._validate_c11b_query_memory_root(
            {checker.C11B_QUERY_MEMORY_ROOT_ID: entry}, baseline_errors
        )
        self.assertEqual([], baseline_errors)

        mutations = {
            "disposition": lambda row: row.__setitem__("disposition", "use_as_is"),
            "strangle_status": lambda row: row.__setitem__("strangle_status", "pending"),
            "owner": lambda row: row.__setitem__("owner", "team-design"),
            "owner_slice": lambda row: row.__setitem__("owner_slice", "DS8"),
            "seed_rule": lambda row: row.__setitem__("seed_rule", "generic_flip"),
            "rationale": lambda row: row.__setitem__("rationale", "generic cache root"),
            "successor": lambda row: row.pop("successor"),
            "successor.unit_id": lambda row: row["successor"].__setitem__(
                "unit_id", "unreviewed-query-successor"
            ),
            "successor.consumer_refs": lambda row: row["successor"].__setitem__(
                "consumer_refs", row["successor"]["consumer_refs"][:-1]
            ),
        }
        for field, mutate in mutations.items():
            with self.subTest(field=field):
                mutation = copy.deepcopy(data)
                target = next(
                    row
                    for row in mutation["entries"]
                    if row["unit_id"] == checker.C11B_QUERY_MEMORY_ROOT_ID
                )
                mutate(target)
                errors = checker.validate_register(
                    mutation, live_probes=False, report_parity=False
                )
                self.assertIn(f"c11b_query_memory_root_drift:{field}", errors)

    def test_c11b_query_memory_root_writer_is_surgical_and_idempotent(self) -> None:
        """Produce the exact owner transition without rewriting adjacent bytes."""
        original = REGISTER_PATH.read_text(encoding="utf-8")

        def entry_span(text: str) -> tuple[int, int]:
            needle = f'"unit_id": "{checker.C11B_QUERY_MEMORY_ROOT_ID}"'
            marker = text.index(needle)
            start = text.rfind("    {", 0, marker) + 4
            _, relative_end = json.JSONDecoder().raw_decode(text[start:])
            return start, start + relative_end

        transitioned = checker._c11b_query_memory_transition_text(original)
        before_start, before_end = entry_span(original)
        after_start, after_end = entry_span(transitioned)
        self.assertEqual(original[:before_start], transitioned[:after_start])
        self.assertEqual(original[before_end:], transitioned[after_end:])
        self.assertEqual(
            transitioned,
            checker._c11b_query_memory_transition_text(transitioned),
        )

        data = json.loads(transitioned)
        errors: list[str] = []
        checker._validate_c11b_query_memory_root(
            {
                checker.C11B_QUERY_MEMORY_ROOT_ID: next(
                    row
                    for row in data["entries"]
                    if row["unit_id"] == checker.C11B_QUERY_MEMORY_ROOT_ID
                )
            },
            errors,
        )
        self.assertEqual([], errors)

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
        refreshed_descriptors = {
            row["finding_id"]: row
            for row in refreshed["supplemental_findings"]
            if row["finding_id"] in descriptor_ids
        }
        self.assertEqual(set(generated_descriptors), set(refreshed_descriptors))
        for finding_id, generated in generated_descriptors.items():
            with self.subTest(finding_id=finding_id):
                if finding_id in checker.AUTHORITY_PRESENTATION_DEBT_SPECS:
                    self.assertEqual(
                        checker._authority_row_semantic_value(generated),
                        checker._authority_row_semantic_value(
                            refreshed_descriptors[finding_id]
                        ),
                    )
                else:
                    self.assertEqual(
                        generated,
                        refreshed_descriptors[finding_id],
                    )
        for field in sorted(set(before) - {"supplemental_findings"}):
            with self.subTest(field=field):
                self.assertEqual(before[field], refreshed[field])
        self.assertEqual(
            19,
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
        self.assertIn(
            "`consumer_missing`, `surface_missing`, `semantic_test_missing`",
            producer_line,
        )
        self.assertIn(str(self._producer_row()["closure_signal"]), producer_line)
        self.assertIn("| — | — |", ordinary_line)
        readiness_line = next(
            line
            for line in projection.splitlines()
            if "`producer-binding-readiness-scientific-depth`" in line
        )
        self.assertIn("`artifact_missing`", readiness_line)
        self.assertIn("registered typed refusal", readiness_line)


class DS6RegisterTransitionTests(unittest.TestCase):
    """Prove DS6 register rows follow measured evidence lifecycles."""

    def test_c04_open_rendered_contrast_row_covers_the_exact_typed_registry(
        self,
    ) -> None:
        expected_sources = [
            {
                "sourceId": "badge-neutral",
                "ownerCluster": "C01",
                "component": "Badge",
                "selector": '[data-opaque-contrast-source="badge-neutral"]',
            },
            {
                "sourceId": "provenance-popover",
                "ownerCluster": "C06",
                "component": "ProvenancePopover",
                "selector": '[data-opaque-contrast-source="provenance-popover"]',
            },
            {
                "sourceId": "provenance-mini-graph",
                "ownerCluster": "C06",
                "component": "ProvenanceMiniGraph",
                "selector": '[data-opaque-contrast-source="provenance-mini-graph"]',
            },
            {
                "sourceId": "time-semantics-label",
                "ownerCluster": "C09",
                "component": "TimeSemanticsLabel",
                "selector": '[data-opaque-contrast-source="time-semantics-label"]',
            },
            {
                "sourceId": "candidate-frame",
                "ownerCluster": "C14",
                "component": "CandidateFrame",
                "selector": '[data-opaque-contrast-source="candidate-frame"]',
            },
            {
                "sourceId": "negative-certificate-card",
                "ownerCluster": "C14",
                "component": "NegativeCertificateCard",
                "selector": '[data-opaque-contrast-source="negative-certificate-card"]',
            },
            {
                "sourceId": "weakest-link-explainer",
                "ownerCluster": "C14",
                "component": "WeakestLinkExplainer",
                "selector": '[data-opaque-contrast-source="weakest-link-explainer"]',
            },
        ]
        self.assertEqual(  # noqa: PT009 - this module is a unittest suite
            checker.C04_RENDERED_CONTRAST_REGISTRY_SHA256,
            checker._canonical_sha256(expected_sources),
        )
        self.assertEqual(  # noqa: PT009 - this module is a unittest suite
            "d455a84a63b3fbcb1e890d913d3dad87e6abe47a69a593b4d7575f0afc743eba",
            checker.C04_RENDERED_CONTRAST_OWNER_AST_SHA256,
        )
        self.assertEqual(  # noqa: PT009 - this module is a unittest suite
            expected_sources,
            checker._c04_rendered_contrast_source_rows(),
        )

        row = checker._c04_rendered_contrast_finding()
        expected_row = {
            "finding_id": "baseline-test-a11y-rendered-contrast-incomplete-debt",
            "finding_kind": "baseline_test_debt",
            "disposition": "rebind_pending",
            "status": "open_debt",
            "evidence_refs": [
                "apps/runtime-dashboard/src/test/a11y/opaqueBackgroundContrast.ts",
                "apps/runtime-dashboard/src/test/a11y/opaqueBackgroundContrast.test.ts",
                "apps/runtime-dashboard/src/test/a11y/OpaqueBackgroundContrast.stories.tsx",
            ],
            "owner_slice": "DS6",
            "decision_date": "2026-08-11",
            "rationale": (
                "C01/C06/C09/C14 comprise seven declared source identities. Axe "
                "incomplete nodes are neither passes, source-attributed receipts, nor "
                "denominator members; closure requires 7/7 numeric WCAG-AA receipts "
                "on an opaque real-browser background."
            ),
        }
        self.assertEqual(row, expected_row)  # noqa: PT009 - unittest suite

    def test_c04_source_registry_rejects_semantic_drift_not_text_layout(
        self,
    ) -> None:
        source = checker.C04_RENDERED_CONTRAST_SOURCE_PATH.read_text(
            encoding="utf-8"
        )
        reformatted = source.replace(
            'sourceId: "badge-neutral",',
            'sourceId:\n      "badge-neutral",',
            1,
        )
        self.assertEqual(  # noqa: PT009 - this module is a unittest suite
            checker._c04_rendered_contrast_source_rows(),
            checker._c04_rendered_contrast_source_rows(reformatted),
        )

        first_start = source.index('  {\n    sourceId: "badge-neutral"')
        second_start = source.index('  {\n    sourceId: "provenance-popover"')
        third_start = source.index('  {\n    sourceId: "provenance-mini-graph"')
        first_row = source[first_start:second_start]
        second_row = source[second_start:third_start]
        reordered = (
            source[:first_start]
            + second_row
            + first_row
            + source[third_start:]
        )
        namespace_wrapped = source.replace(
            "export const OPAQUE_BACKGROUND_CONTRAST_SOURCES",
            "export namespace Hidden {\nexport const OPAQUE_BACKGROUND_CONTRAST_SOURCES",
            1,
        ).replace("] as const;", "] as const;\n}", 1)
        registry_start = source.index("[", source.index("OPAQUE_BACKGROUND"))
        registry_end = source.index("] as const;", registry_start) + 1
        registry_literal = source[registry_start:registry_end]

        corruptions = {
            "renamed": source.replace(
                'sourceId: "badge-neutral"', 'sourceId: "badge"', 1
            ),
            "duplicate": source.replace(
                'sourceId: "provenance-popover"',
                'sourceId: "badge-neutral"',
                1,
            ),
            "wrong-cluster": source.replace(
                'ownerCluster: "C01"', 'ownerCluster: "C14"', 1
            ),
            "wrong-component": source.replace(
                'component: "Badge"', 'component: "Text"', 1
            ),
            "wrong-selector": source.replace(
                '[data-opaque-contrast-source="badge-neutral"]',
                '[data-opaque-contrast-source="badge"]',
                1,
            ),
            "extra-field": source.replace(
                'component: "Badge",',
                'component: "Badge",\n    invented: "authority",',
                1,
            ),
            "unexported": source.replace(
                "export const OPAQUE_BACKGROUND_CONTRAST_SOURCES",
                "const OPAQUE_BACKGROUND_CONTRAST_SOURCES",
                1,
            ),
            "mutable": source.replace(
                "export const OPAQUE_BACKGROUND_CONTRAST_SOURCES",
                "export let OPAQUE_BACKGROUND_CONTRAST_SOURCES",
                1,
            ),
            "spread": source.replace(
                "] as const;",
                "  ...inventedSources(),\n] as const;",
                1,
            ),
            "eighth-source": source.replace(
                "] as const;",
                (
                    '  { sourceId: "invented", ownerCluster: "C14", '
                    'component: "Invented", selector: '
                    "'[data-opaque-contrast-source=\"invented\"]' },\n"
                    "] as const;"
                ),
                1,
            ),
            "duplicate-binding": (
                source
                + "\nexport const OPAQUE_BACKGROUND_CONTRAST_SOURCES = [] as const;\n"
            ),
            "missing-source": source[:first_start] + source[second_start:],
            "reordered": reordered,
            "computed-key": source.replace("sourceId:", '["sourceId"]:', 1),
            "template-value": source.replace(
                'sourceId: "badge-neutral"',
                "sourceId: `badge-neutral`",
                1,
            ),
            "missing-const-assertion": source.replace("] as const;", "];", 1),
            "namespace-owned": namespace_wrapped,
            "ambient": source.replace(
                "export const OPAQUE_BACKGROUND_CONTRAST_SOURCES",
                "export declare const OPAQUE_BACKGROUND_CONTRAST_SOURCES",
                1,
            ),
            "runtime-mutation": (
                source
                + "\n;(OPAQUE_BACKGROUND_CONTRAST_SOURCES as unknown as "
                "Array<unknown>).pop();\n"
            ),
            "esm-only-runtime-mutation": (
                source
                + '\nif (!("module" in globalThis)) {\n'
                "  ;(OPAQUE_BACKGROUND_CONTRAST_SOURCES as unknown as "
                "Array<unknown>).pop();\n}\n"
            ),
            "conflicting-export-alias": (
                source
                + "\nconst forgedRegistry = OPAQUE_BACKGROUND_CONTRAST_SOURCES;\n"
                "export { forgedRegistry as OPAQUE_BACKGROUND_CONTRAST_SOURCES };\n"
            ),
            "alternate-export-alias": (
                source
                + "\nexport { OPAQUE_BACKGROUND_CONTRAST_SOURCES as SECOND_NAME };\n"
            ),
            "default-export-alias": (
                source
                + "\nexport { OPAQUE_BACKGROUND_CONTRAST_SOURCES as default };\n"
            ),
            "unused-dynamic-import": (
                source
                + '\nexport async function unused() { return import("./invented"); }\n'
            ),
            "commonjs-export-forgery": (
                source
                + "\ndeclare const exports: Record<string, unknown>;\n"
                + ";(OPAQUE_BACKGROUND_CONTRAST_SOURCES as unknown as "
                "Array<unknown>).pop();\n"
                + "exports.OPAQUE_BACKGROUND_CONTRAST_SOURCES = "
                + registry_literal
                + ";\n"
            ),
            "transitive-map-mutation": (
                source
                + '\n;(SOURCE_BY_ID.get("badge-neutral") as any).sourceId = "forged";\n'
            ),
            "return-line-terminator": source.replace(
                "return false;",
                "return\nfalse;",
                1,
            ),
            "declaration-any": source.replace(
                "OPAQUE_BACKGROUND_CONTRAST_SOURCES = [",
                "OPAQUE_BACKGROUND_CONTRAST_SOURCES: any = [",
                1,
            ),
            "property-any": source.replace(
                'sourceId: "badge-neutral"',
                'sourceId: ("badge-neutral" as any)',
                1,
            ),
            "row-any": source.replace(
                '  },\n  {\n    sourceId: "provenance-popover"',
                '  } as any,\n  {\n    sourceId: "provenance-popover"',
                1,
            ),
            "array-any": source.replace(
                "] as const;",
                "] as any as const;",
                1,
            ),
        }
        for name, mutation in corruptions.items():
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(  # noqa: PT027 - unittest suite
                    ValueError,
                    "c04_rendered_contrast_source_registry_drift",
                ),
            ):
                checker._c04_rendered_contrast_finding(source_text=mutation)

    def test_c06_repaired_row_binds_the_exact_landed_browser_receipt(self) -> None:
        receipt = checker._c06_c16_contrast_receipt()
        self.assertEqual(  # noqa: PT009 - unittest suite
            {
                "receipt_kind": "landed_opaque_storybook_release",
                "producer_revision": (
                    "97d0c620836a3e6d33c347a1f7f563aaa9177d0c"
                ),
                "entry_revision": "41a2020d5c2097c30c94807737ba6d3a80323d2e",
                "source_delta_sha256": (
                    "800225190d7a47f68b585db206d6b634bd1c7787ab27bb9c5b8e8e1f5fc2bf8a"
                ),
                "wall_duration_seconds": 14.02,
                "story_files": {"total": 1, "passed": 1, "failed": 0},
                "tests": {"total": 1, "passed": 1, "failed": 0},
                "custom_source_observations": {
                    "sources": {"total": 7, "passed": 7, "failed": 0},
                    "violation_count": 0,
                    "incomplete_count": 0,
                    "numeric_source_receipts": True,
                    "atomic": True,
                },
                "automatic_a11y_meta_report": {
                    "incomplete_count": 3,
                    "color_contrast_incomplete_count": 1,
                    "source_attribution": "unattributed",
                    "denominator_membership": (
                        "outside_custom_source_observations"
                    ),
                },
                "raw_receipt": {
                    "format": "storybook_json",
                    "bytes": 163320,
                    "sha256": (
                        "a608e9b606e50b75bef602136e0f9b0c47406dfedf0f68888b792b781e99eafa"
                    ),
                    "availability": "not_persisted_in_repository",
                },
                "source_registry_sha256": (
                    "5f69573f7c1cbb27665d0e7696901f194a51a16ca55f6a827095fd691d761177"
                ),
                "owner_ast_sha256": (
                    "d455a84a63b3fbcb1e890d913d3dad87e6abe47a69a593b4d7575f0afc743eba"
                ),
                "release_provenance": "recomputed",
                "measurement_provenance": "task_authoritative_landed_release",
                "authority_purpose": "c16_landed_opaque_storybook_release",
                "source_refs": [
                    {
                        "path": source_ref,
                        "content_sha256": source_sha256,
                    }
                    for source_ref, source_sha256 in (
                        checker.C03_RECEIPT_SOURCE_SHA256.items()
                    )
                ],
            },
            receipt,
        )

        expected_row = {
            **checker._c04_rendered_contrast_finding(),
            "status": "repaired",
            "repair_commit": "97d0c620836a3e6d33c347a1f7f563aaa9177d0c",
        }
        self.assertEqual(  # noqa: PT009 - unittest suite
            expected_row,
            checker._c06_rendered_contrast_finding(),
        )
        stored = next(
            finding
            for finding in checker._supplemental_findings()
            if finding["finding_id"]
            == "baseline-test-a11y-rendered-contrast-incomplete-debt"
        )
        self.assertEqual(expected_row, stored)  # noqa: PT009 - unittest suite

    def test_c06_receipt_and_current_evidence_drift_fail_closed(self) -> None:
        revision = "97d0c620836a3e6d33c347a1f7f563aaa9177d0c"
        plan_ref = "docs/plans/active/atlas-slices/DS6-evidence-workflow.md"
        journal_ref = (
            "docs/plans/active/atlas-slices/DS6-evidence-workflow-journal.md"
        )
        plan_text = checker._c03_git_text(
            "show",
            f"{revision}:policy-engine/{plan_ref}",
        )
        journal_text = checker._c03_git_text(
            "show",
            f"{revision}:policy-engine/{journal_ref}",
        )
        source_corruptions = {
            "six-of-seven": (
                plan_text.replace("exactly 7/7", "exactly 6/7", 1),
                journal_text,
            ),
            "wrong-duration": (
                plan_text.replace("14.02 s", "14.03 s", 1),
                journal_text,
            ),
            "wrong-raw-hash": (
                plan_text.replace(
                    "a608e9b606e50b75bef602136e0f9b0c47406dfedf0f68888b792b781e99eafa",
                    "0" * 64,
                    1,
                ),
                journal_text,
            ),
            "invalidated-attempt-substitution": (
                plan_text,
                journal_text.replace("14.02 s", "14.57 s", 1),
            ),
            "custom-incomplete": (
                plan_text,
                journal_text.replace(
                    "zero violations/incompletes in the seven custom source observations",
                    "one incomplete in the seven custom source observations",
                    1,
                ),
            ),
            "automatic-meta-incomplete-count": (
                plan_text,
                journal_text.replace(
                    "meta-report separately retains three",
                    "meta-report separately retains zero",
                    1,
                ),
            ),
            "automatic-meta-contrast-count": (
                plan_text,
                journal_text.replace(
                    "incomplete nodes, including one `color-contrast` incomplete",
                    "incomplete nodes, including zero `color-contrast` incomplete",
                    1,
                ),
            ),
            "automatic-meta-denominator": (
                plan_text,
                journal_text.replace(
                    "They are outside the seven custom\nsource observations",
                    "They are inside the seven custom\nsource observations",
                    1,
                ),
            ),
        }
        for name, (mutated_plan, mutated_journal) in source_corruptions.items():
            with (
                self.subTest(source=name),
                self.assertRaisesRegex(  # noqa: PT027 - unittest suite
                    ValueError,
                    "C16 contrast receipt",
                ),
            ):
                checker._c06_c16_contrast_receipt_from_sources(
                    mutated_plan,
                    mutated_journal,
                )

        current_evidence = {
            source_ref: (checker.REPO_ROOT / source_ref).read_bytes()
            for source_ref in checker.C04_RENDERED_CONTRAST_EVIDENCE_REFS
        }
        for source_ref, source_bytes in current_evidence.items():
            mutation = dict(current_evidence)
            mutation[source_ref] = source_bytes + b"\n// drift\n"
            with (
                self.subTest(current_evidence=source_ref),
                self.assertRaisesRegex(  # noqa: PT027 - unittest suite
                    ValueError,
                    "C16 contrast current evidence drift",
                ),
            ):
                checker._c06_verify_c16_contrast_evidence(mutation)

    def test_c06_transition_is_surgical_idempotent_and_rejects_bypass(self) -> None:
        finding_id = "baseline-test-a11y-rendered-contrast-incomplete-debt"
        register_ref = (
            "policy-engine/architecture/atlas_surfaces/"
            "frontend-disposition-register.json"
        )
        open_text = checker._c03_git_text(
            "show",
            f"{checker.C06_C04_ADMISSION_COMMIT}:{register_ref}",
        )
        repaired_text = checker._c06_rendered_contrast_transition_text(open_text)
        self.assertEqual(  # noqa: PT009 - unittest suite
            repaired_text,
            checker._c06_rendered_contrast_transition_text(repaired_text),
        )

        _open_start, _open_end, open_rows = checker._supplemental_section(open_text)
        _repaired_start, _repaired_end, repaired_rows = checker._supplemental_section(
            repaired_text
        )
        self.assertEqual(  # noqa: PT009 - unittest suite
            [row for row in open_rows if row[0] != finding_id],
            [row for row in repaired_rows if row[0] != finding_id],
        )
        open_row = json.loads(next(row for row in open_rows if row[0] == finding_id)[1])
        repaired_row = json.loads(
            next(row for row in repaired_rows if row[0] == finding_id)[1]
        )
        self.assertEqual(  # noqa: PT009 - unittest suite
            checker._c04_rendered_contrast_finding(),
            open_row,
        )
        self.assertEqual(  # noqa: PT009 - unittest suite
            checker._c06_rendered_contrast_finding(),
            repaired_row,
        )
        with self.assertRaisesRegex(  # noqa: PT027 - unittest suite
            ValueError,
            "dedicated C06 transition",
        ):
            checker._refresh_supplemental_findings_text(open_text)

        _section_start, section_end, spans = checker._supplemental_section_spans(
            open_text
        )
        target = next(span for span in spans if span[0] == finding_id)

        def replace_target(row: dict[str, object]) -> str:
            return (
                open_text[: target[1]]
                + checker._render_supplemental_finding(row)
                + open_text[target[2] + 1 :]
            )

        premature = {**open_row, "status": "repaired"}
        wrong_commit = {
            **premature,
            "repair_commit": "0" * 40,
        }
        wrong_rationale = {**open_row, "rationale": "fabricated"}
        missing = checker._remove_supplemental_finding_text(open_text, finding_id)
        duplicate = (
            open_text[:section_end]
            + ",\n    "
            + checker._render_supplemental_finding(open_row)
            + open_text[section_end:]
        )
        corruptions = {
            "premature-repair": replace_target(premature),
            "wrong-repair-commit": replace_target(wrong_commit),
            "wrong-open-rationale": replace_target(wrong_rationale),
            "missing": missing,
            "duplicate": duplicate,
        }
        for name, mutation in corruptions.items():
            with (
                self.subTest(predecessor=name),
                self.assertRaisesRegex(  # noqa: PT027 - unittest suite
                    ValueError,
                    "C06 rendered contrast transition rejected",
                ),
            ):
                checker._c06_rendered_contrast_transition_text(mutation)

        original_git_text = checker._c03_git_text

        def reject_missing_c04_ancestry(*arguments: str) -> str:
            if arguments == (
                "merge-base",
                "--is-ancestor",
                checker.C06_C04_ADMISSION_COMMIT,
                "HEAD",
            ):
                raise ValueError("C04 admission ancestry missing")
            return original_git_text(*arguments)

        with (
            mock.patch.object(
                checker,
                "_c03_git_text",
                side_effect=reject_missing_c04_ancestry,
            ),
            self.assertRaisesRegex(  # noqa: PT027 - unittest suite
                ValueError,
                "C04 admission ancestry missing",
            ),
        ):
            checker._c06_rendered_contrast_transition_text(open_text)

    def test_c06_write_mode_rejects_every_early_print_mode(self) -> None:
        print_flags = (
            "--print-c21b-authority-identity-literals",
            "--print-c21b-descriptor-identities",
            "--print-c21b-authority-partition-hashes",
        )
        for print_flag in print_flags:
            with self.subTest(print_flag=print_flag), mock.patch(
                "sys.stdout",
                new=io.StringIO(),
            ):
                self.assertEqual(  # noqa: PT009 - unittest suite
                    1,
                    checker.main(
                        [
                            "--write-c06-rendered-contrast-resolution",
                            "--write-report",
                            print_flag,
                        ]
                    ),
                )

    def test_c06_stored_repaired_row_rejects_drift_in_every_governed_field(
        self,
    ) -> None:
        finding_id = "baseline-test-a11y-rendered-contrast-incomplete-debt"
        validator = getattr(
            checker,
            "_validate_ds6_register_transition_findings",
            None,
        )
        if not callable(validator):
            raise AssertionError("DS6 transition-row validator is missing")
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        stored = [
            row
            for row in data["supplemental_findings"]
            if row["finding_id"] == finding_id
        ]
        self.assertEqual(1, len(stored))  # noqa: PT009 - unittest suite
        corruptions = {
            "finding_id": finding_id + "-drift",
            "finding_kind": "dependency_declaration",
            "disposition": "use_as_is",
            "status": "open_debt",
            "evidence_refs": ["docs/fabricated.md"],
            "owner_slice": "DS4",
            "decision_date": "2026-08-20",
            "repair_commit": "0" * 40,
            "closure_signal": "fabricated but schema-valid optional field",
            "rationale": "fabricated",
        }
        for field, value in corruptions.items():
            with self.subTest(field=field):
                mutation = copy.deepcopy(data)
                row = next(
                    item
                    for item in mutation["supplemental_findings"]
                    if item["finding_id"] == finding_id
                )
                row[field] = value
                errors: list[str] = []
                validator(mutation, errors)
                self.assertIn(  # noqa: PT009 - this module is a unittest suite
                    f"ds6_register_transition_drift:{finding_id}", errors
                )

        missing_commit = copy.deepcopy(data)
        next(
            row
            for row in missing_commit["supplemental_findings"]
            if row["finding_id"] == finding_id
        ).pop("repair_commit")
        errors = []
        validator(missing_commit, errors)
        self.assertIn(  # noqa: PT009 - unittest suite
            f"ds6_register_transition_drift:{finding_id}", errors
        )

        for population, mutation in {
            "missing": {
                **data,
                "supplemental_findings": [
                    row
                    for row in data["supplemental_findings"]
                    if row["finding_id"] != finding_id
                ],
            },
            "duplicate": {
                **data,
                "supplemental_findings": [
                    *data["supplemental_findings"],
                    copy.deepcopy(stored[0]),
                ],
            },
        }.items():
            with self.subTest(population=population):
                errors = []
                validator(mutation, errors)
                self.assertIn(  # noqa: PT009 - this module is a unittest suite
                    f"ds6_register_transition_drift:{finding_id}", errors
                )

    def test_c03_repaired_i18n_row_is_bound_to_the_c16_receipt(self) -> None:
        baseline = checker._load_json(checker.BASELINE_PATH)
        baseline["vitest"] = {
            **baseline["vitest"],
            **copy.deepcopy(checker._c03_c16_receipt()),
        }
        original_load = checker._load_json

        def load_with_resolved_baseline(path: Path) -> dict[str, object]:
            if path == checker.BASELINE_PATH:
                return copy.deepcopy(baseline)
            return original_load(path)

        with mock.patch.object(checker, "_load_json", side_effect=load_with_resolved_baseline):
            row = next(
                finding
                for finding in checker._supplemental_findings()
                if finding["finding_id"] == "baseline-test-i18n-count-debt"
            )

        expected = {
                "finding_id": "baseline-test-i18n-count-debt",
                "finding_kind": "baseline_test_debt",
                "disposition": "rebind_pending",
                "status": "repaired",
                "evidence_refs": [
                    "architecture/atlas_surfaces/"
                    "frontend-baseline-debt-manifest.json#tests/i18n-count"
                ],
                "owner_slice": "DS6",
                "decision_date": "2026-07-17",
                "repair_commit": "97d0c620836a3e6d33c347a1f7f563aaa9177d0c",
                "rationale": (
                    "The governed Vitest lifecycle admits exactly the three historical DS6 "
                    "count-message identities while open or the C16 full-suite empty "
                    "failure set when repaired."
                ),
            }
        if row != expected:
            raise AssertionError(f"C03 row drift: {row!r}")

    def test_c03_stored_row_rejects_drift_in_every_governed_field(self) -> None:
        validator = getattr(
            checker, "_validate_ds6_register_transition_findings", None
        )
        if not callable(validator):
            raise AssertionError("DS6 transition-row validator is missing")
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        stored = next(
            row
            for row in data["supplemental_findings"]
            if row["finding_id"] == "baseline-test-i18n-count-debt"
        )
        corruptions = {
            "finding_kind": "dependency_declaration",
            "disposition": "use_as_is",
            "status": "open_debt",
            "evidence_refs": ["docs/fabricated.md"],
            "owner_slice": "DS4",
            "decision_date": "2026-08-20",
            "repair_commit": "d01eaa572",
            "rationale": "fabricated",
        }
        for field, value in corruptions.items():
            with self.subTest(field=field):
                mutation = copy.deepcopy(data)
                row = next(
                    item
                    for item in mutation["supplemental_findings"]
                    if item["finding_id"] == stored["finding_id"]
                )
                row[field] = value
                errors: list[str] = []
                validator(mutation, errors)
                _expect = f"ds6_register_transition_drift:{stored['finding_id']}"
                if _expect not in errors:
                    raise AssertionError(f"stored C03 {field} drift escaped: {errors}")


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

        navigation_only_reorder = copy.deepcopy(data)
        row = next(
            item
            for item in navigation_only_reorder["supplemental_findings"]
            if item["finding_id"]
            == "authority-presentation-badge-compound-decision-grade"
        )
        row["authority_sink"]["consumer_sites"].reverse()
        for receipt in row["authority_sink"]["consumer_sites"]:
            receipt["line"] += 100
        self.assertEqual(
            [],
            checker._authority_presentation_errors(
                navigation_only_reorder, live_probes=False
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
        site = fingerprint_drift["badgeSites"][0]
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

    def test_unique_content_relocates_after_a_navigation_selected_sibling_is_removed(self) -> None:
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
            [],
            checker._validate_typescript_reference_identity(reference, {source_path: moved}),
        )
        self.assertNotIn("navigation_hint", reference["encoded_identity"])

    def test_duplicate_canonical_candidates_are_ambiguous_after_relocation(self) -> None:
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
            ["typescript_reference_binding_ambiguous"],
            checker._validate_typescript_reference_identity(reference, {source_path: duplicated_badges}),
        )

    def test_unique_bound_content_relocates_past_a_distinct_sibling(self) -> None:
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
            [],
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

    def test_generated_schema_property_is_owner_qualified_and_fails_closed(self) -> None:
        """Generated fields bind their schema owner, content, and unique resolution."""
        source_path = "packages/runtime-api-client/types.ts"
        source = (checker.REPO_ROOT / source_path).read_text(encoding="utf-8")
        discriminator = (
            "components.schemas."
            "polisyos__core__contracts__runtime__LineageRef-Output.status"
        )
        owner_facts = checker._typescript_reference_construct_facts(
            {source_path: source},
            source_path=source_path,
            role="generated_schema_property",
            discriminator=discriminator,
        )
        assert len(owner_facts["matches"]) == 1  # noqa: S101
        target_match = owner_facts["matches"][0]
        navigation_line = target_match["startLine"]
        legacy_identity = checker._typescript_reference_identity(
            {source_path: source},
            source_path=source_path,
            role="type_property",
            discriminator="components.status",
            navigation_hint=navigation_line,
        )
        _legacy_path, _legacy_marker, legacy_encoded = legacy_identity[
            "encoded_identity"
        ].partition("#ts-identity=")
        legacy_payload = json.loads(
            base64.urlsafe_b64decode(
                legacy_encoded + "=" * (-len(legacy_encoded) % 4)
            )
        )
        legacy_facts = checker._typescript_reference_construct_facts(
            {source_path: source},
            source_path=source_path,
            role="type_property",
            discriminator="components.status",
        )
        relocation_candidates = [
            match
            for match in legacy_facts["matches"]
            if match["declarationChain"] == legacy_payload["declaration_chain"]
            and match["normalizedTokensSha256"]
            == legacy_payload["normalized_tokens_sha256"]
        ]
        expected_candidates = {
            "components.schemas.LineageGraphView.status",
            "components.schemas.LineageRef-Input.status",
            "components.schemas.QuantityCoverageEntry.status",
            (
                "components.schemas."
                "polisyos__core__contracts__runtime__LineageRef-Output.status"
            ),
            (
                "components.schemas."
                "polisyos__fabric__evidence__decision_data__LineageRef.status"
            ),
        }
        assert {  # noqa: S101
            match["generatedSchemaProperty"] for match in relocation_candidates
        } == expected_candidates

        identity = checker._typescript_reference_identity(
            {source_path: source},
            source_path=source_path,
            role="generated_schema_property",
            discriminator=discriminator,
            navigation_hint=navigation_line,
        )
        _prefix, _marker, encoded = identity["encoded_identity"].partition(
            "#ts-identity="
        )
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        )
        assert payload["version"] == 1  # noqa: S101
        assert payload["role"] == "generated_schema_property"  # noqa: S101
        assert not any("line" in key for key in payload)  # noqa: S101
        assert "navigation_hint" not in identity["encoded_identity"]  # noqa: S101

        lines = source.splitlines(keepends=True)
        target_index = navigation_line - 1
        target_line = lines[target_index]
        owner_index = next(
            index
            for index in range(target_index - 1, -1, -1)
            if '"polisyos__core__contracts__runtime__LineageRef-Output": {'
            in lines[index]
        )
        moved_lines = list(lines)
        moved_status = moved_lines.pop(target_index)
        moved_lines.insert(owner_index + 1, moved_status)
        moved = "\n" + "".join(moved_lines)
        assert (  # noqa: S101
            checker._validate_typescript_reference_identity(
                identity, {source_path: moved}
            )
            == []
        )

        def replace_target_line(replacement: str) -> str:
            changed = list(lines)
            changed[target_index] = replacement
            return "".join(changed)

        renamed = replace_target_line(target_line.replace("status:", "state:"))
        removed = replace_target_line("")
        for mutation in (renamed, removed):
            assert checker._validate_typescript_reference_identity(  # noqa: S101
                identity, {source_path: mutation}
            ) == ["typescript_reference_binding_missing_or_renamed"]

        drifted = replace_target_line(
            target_line.replace('"untraced"', '"unknown"')
        )
        assert checker._validate_typescript_reference_identity(  # noqa: S101
            identity, {source_path: drifted}
        ) == ["typescript_reference_content_drift"]

        duplicated_lines = list(lines)
        duplicated_lines.insert(target_index + 1, target_line)
        duplicated = "".join(duplicated_lines)
        assert checker._validate_typescript_reference_identity(  # noqa: S101
            identity, {source_path: duplicated}
        ) == ["typescript_reference_binding_ambiguous"]

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

    def test_c21d_real_composer_move_relocates_unique_badges_and_keeps_reds(self) -> None:
        """Replay the seven Badge moves that stopped C13b-R6, including all reds."""
        source_path = (
            "apps/runtime-dashboard/src/features/composer/routes/"
            "ComposerModeSections.tsx"
        )

        def historical_source(commit: str) -> str:
            return subprocess.run(  # noqa: S603
                ["git", "show", f"{commit}:policy-engine/{source_path}"],  # noqa: S607
                cwd=checker.REPO_ROOT.parent,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout

        original = historical_source("f77850487")
        moved = historical_source("a3ad1e615")
        shifts = {
            324: 327,
            545: 548,
            641: 644,
            777: 780,
            876: 879,
            1220: 1268,
            1644: 1701,
        }
        identities = {
            original_line: checker._typescript_reference_identity(
                {source_path: original},
                source_path=source_path,
                role="jsx_opening",
                discriminator="Badge",
                navigation_hint=original_line,
            )
            for original_line in shifts
        }
        moved_identities = {
            original_line: checker._typescript_reference_identity(
                {source_path: moved},
                source_path=source_path,
                role="jsx_opening",
                discriminator="Badge",
                navigation_hint=moved_line,
            )
            for original_line, moved_line in shifts.items()
        }
        original_keys = checker._typescript_reference_hybrid_keys(list(identities.values()))
        moved_keys = checker._typescript_reference_hybrid_keys(
            list(moved_identities.values())
        )
        self.assertEqual(original_keys, moved_keys)  # noqa: PT009
        self.assertTrue(  # noqa: PT009
            set(original_keys) <= set(checker.FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS)
        )
        moved_facts = checker._typescript_reference_construct_facts(
            {source_path: moved},
            source_path=source_path,
            role="jsx_opening",
            discriminator="Badge",
        )
        moved_lines_by_chain = {
            tuple(match["declarationChain"]): match["startLine"]
            for match in moved_facts["matches"]
        }
        self.assertEqual(  # noqa: PT009
            shifts,
            {
                original_line: moved_lines_by_chain[
                    tuple(json.loads(identity["declaration_chain"]))
                ]
                for original_line, identity in identities.items()
            },
        )
        for original_line, identity in identities.items():
            with self.subTest(original_line=original_line):
                self.assertEqual(
                    [],
                    checker._validate_typescript_reference_identity(
                        identity, {source_path: moved}
                    ),
                )

        target_line = shifts[1220]

        def replace_target_line(source: str, old: str, new: str) -> str:
            lines = source.splitlines(keepends=True)
            self.assertIn(old, lines[target_line - 1])  # noqa: PT009
            lines[target_line - 1] = lines[target_line - 1].replace(old, new, 1)
            return "".join(lines)

        renamed = replace_target_line(moved, "<Badge", "<RenamedBadge")
        renamed_lines = renamed.splitlines(keepends=True)
        closing_index = next(
            index
            for index in range(target_line, len(renamed_lines))
            if "</Badge>" in renamed_lines[index]
        )
        renamed_lines[closing_index] = renamed_lines[closing_index].replace(
            "</Badge>", "</RenamedBadge>", 1
        )
        renamed = "".join(renamed_lines)
        self.assertEqual(
            ["typescript_reference_binding_missing_or_renamed"],
            checker._validate_typescript_reference_identity(
                identities[1220], {source_path: renamed}
            ),
        )

        rewritten = replace_target_line(
            moved,
            "<Badge",
            '<Badge data-c21d-content="changed"',
        )
        self.assertEqual(
            ["typescript_reference_content_drift"],
            checker._validate_typescript_reference_identity(
                identities[1220], {source_path: rewritten}
            ),
        )

        lines = moved.splitlines(keepends=True)
        closing_index = next(
            index
            for index in range(target_line, len(lines))
            if "</Badge>" in lines[index]
        )
        badge_block = lines[target_line - 1 : closing_index + 1]
        ambiguous = "".join(
            lines[: closing_index + 1]
            + badge_block
            + lines[closing_index + 1 :]
        )
        self.assertEqual(
            ["typescript_reference_binding_ambiguous"],
            checker._validate_typescript_reference_identity(
                identities[1220], {source_path: ambiguous}
            ),
        )

    def test_c21d_governed_batch_gate_replays_real_composer_move_and_reds(self) -> None:
        """The production batch gate, not only its standalone helper, owns relocation."""
        source_path = (
            "apps/runtime-dashboard/src/features/composer/routes/"
            "ComposerModeSections.tsx"
        )

        def historical_source(commit: str) -> str:
            return subprocess.run(  # noqa: S603
                ["git", "show", f"{commit}:policy-engine/{source_path}"],  # noqa: S607
                cwd=checker.REPO_ROOT.parent,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout

        original = historical_source("f77850487")
        moved = historical_source("a3ad1e615")
        shifts = {
            324: 327,
            545: 548,
            641: 644,
            777: 780,
            876: 879,
            1220: 1268,
            1644: 1701,
        }
        references = [
            checker._typescript_reference_identity(
                {source_path: original},
                source_path=source_path,
                role="jsx_opening",
                discriminator="Badge",
                navigation_hint=original_line,
            )["encoded_identity"]
            for original_line in shifts
        ]
        target_reference = references[list(shifts).index(1220)]
        target_line = shifts[1220]
        target_path = checker.REPO_ROOT / source_path
        original_read_text = Path.read_text

        def governed_errors(source: str) -> list[str]:
            def read_text_override(
                path: Path, *args: object, **kwargs: object
            ) -> str:
                if path == target_path:
                    return source
                return original_read_text(path, *args, **kwargs)

            with mock.patch.object(Path, "read_text", new=read_text_override):
                return checker._typescript_identity_reference_errors(references)

        self.assertEqual([], governed_errors(moved))  # noqa: PT009

        def replace_target_line(source: str, old: str, new: str) -> str:
            lines = source.splitlines(keepends=True)
            self.assertIn(old, lines[target_line - 1])  # noqa: PT009
            lines[target_line - 1] = lines[target_line - 1].replace(old, new, 1)
            return "".join(lines)

        renamed = replace_target_line(moved, "<Badge", "<RenamedBadge")
        renamed_lines = renamed.splitlines(keepends=True)
        closing_index = next(
            index
            for index in range(target_line, len(renamed_lines))
            if "</Badge>" in renamed_lines[index]
        )
        renamed_lines[closing_index] = renamed_lines[closing_index].replace(
            "</Badge>", "</RenamedBadge>", 1
        )
        self.assertEqual(  # noqa: PT009
            [
                "typescript_reference_binding_missing_or_renamed:"
                + target_reference
            ],
            governed_errors("".join(renamed_lines)),
        )

        rewritten = replace_target_line(
            moved,
            "<Badge",
            '<Badge data-c21d-content="changed"',
        )
        self.assertEqual(  # noqa: PT009
            ["typescript_reference_content_drift:" + target_reference],
            governed_errors(rewritten),
        )

        lines = moved.splitlines(keepends=True)
        closing_index = next(
            index
            for index in range(target_line, len(lines))
            if "</Badge>" in lines[index]
        )
        badge_block = lines[target_line - 1 : closing_index + 1]
        ambiguous = "".join(
            lines[: closing_index + 1]
            + badge_block
            + lines[closing_index + 1 :]
        )
        self.assertEqual(  # noqa: PT009
            ["typescript_reference_binding_ambiguous:" + target_reference],
            governed_errors(ambiguous),
        )

    def test_c21d_ordinary_import_never_executes_identity_parser(self) -> None:
        """Cold ordinary import cannot reach the retired migration binding site."""
        spec = importlib.util.spec_from_file_location(
            "frontend_disposition_checker_c21d_cold_import", CHECKER_PATH
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to load a cold C21d checker module")
        module = importlib.util.module_from_spec(spec)
        with mock.patch.object(
            subprocess,
            "run",
            side_effect=AssertionError("ordinary import executed a subprocess"),
        ):
            spec.loader.exec_module(module)
        self.assertEqual(  # noqa: PT009
            163, len(module.FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS)
        )
        self.assertEqual(  # noqa: PT009
            72, len(module.FROZEN_AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS)
        )

    def test_c21d_retired_address_owners_are_absent_and_counts_are_complete(self) -> None:
        """All fixed migration addresses are gone; line-free owners retain the census."""
        self.assertFalse(hasattr(checker, "BENIGN_BADGE_CLASS_SPECS"))  # noqa: PT009
        self.assertEqual(  # noqa: PT009
            {
                "interaction_or_editor_state": 13,
                "transport_or_runtime_health": 20,
                "workflow_or_lifecycle_display_without_terminality_inference": 24,
                "layout_or_counts": 21,
                "opaque_metadata_or_taxonomy": 25,
            },
            checker.BENIGN_BADGE_CLASS_COUNTS,
        )
        self.assertEqual(103, sum(checker.BENIGN_BADGE_CLASS_COUNTS.values()))  # noqa: PT009
        self.assertEqual(19, len(checker.AUTHORITY_PROP_CLASSIFICATIONS))  # noqa: PT009
        self.assertEqual(  # noqa: PT009
            35,
            sum(
                len(specification["consumer_paths"])
                for specification in checker.AUTHORITY_PROP_CLASSIFICATIONS.values()
            ),
        )
        for specification in checker.AUTHORITY_PROP_CLASSIFICATIONS.values():
            self.assertNotIn("component_declaration_line", specification)  # noqa: PT009
            self.assertNotIn("prop_declaration_line", specification)  # noqa: PT009
            self.assertNotIn("uses", specification)  # noqa: PT009
            self.assertTrue(  # noqa: PT009
                all(
                    isinstance(path, str)
                    for path in specification["consumer_paths"]
                )
            )
        self.assertEqual(27, len(checker.AUTHORITY_BADGE_DEBT_SPECS))  # noqa: PT009
        for specification in checker.AUTHORITY_BADGE_DEBT_SPECS.values():
            self.assertNotIn("locations", specification)  # noqa: PT009
        badge_values = checker.FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS.values()
        self.assertEqual(58, sum(value.startswith("debt:") for value in badge_values))  # noqa: PT009
        prop_records = [
            record
            for records in checker.FROZEN_AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS.values()
            for record in records
        ]
        self.assertEqual(73, len(prop_records))  # noqa: PT009

        raw_address_residuals = {
            "benign_or_count_anchors": 0
            if not hasattr(checker, "BENIGN_BADGE_CLASS_SPECS")
            else sum(checker.BENIGN_BADGE_CLASS_COUNTS.values()),
            "debt_group_bindings": sum(
                len(specification.get("locations", ()))
                for specification in checker.AUTHORITY_BADGE_DEBT_SPECS.values()
            ),
            "prop_addresses": sum(
                int("component_declaration_line" in specification)
                + int("prop_declaration_line" in specification)
                + len(specification.get("uses", ()))
                for specification in checker.AUTHORITY_PROP_CLASSIFICATIONS.values()
            ),
        }
        self.assertEqual(  # noqa: PT009
            {
                "benign_or_count_anchors": (103, 0),
                "debt_group_bindings": (58, 0),
                "prop_addresses": (73, 0),
            },
            {
                "benign_or_count_anchors": (
                    sum(checker.BENIGN_BADGE_CLASS_COUNTS.values()),
                    raw_address_residuals["benign_or_count_anchors"],
                ),
                "debt_group_bindings": (
                    sum(
                        value.startswith("debt:")
                        for value in checker.FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS.values()
                    ),
                    raw_address_residuals["debt_group_bindings"],
                ),
                "prop_addresses": (len(prop_records), raw_address_residuals["prop_addresses"]),
            },
            "ds5_c21d_retired_raw_address_residual_drift",
        )

    def test_c21d_live_register_identity_census_preserves_every_distinct_binding(self) -> None:
        """Derive C21d's collision-safe identity census from every stored TypeScript ref."""
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        references = DS5LineAddressCensusTests._live_references(data)
        identity_references = [
            reference for reference in references if "#ts-identity=" in reference
        ]
        distinct_references = sorted(set(identity_references))
        identities = [
            checker._typescript_reference_identity_record(reference)
            for reference in distinct_references
        ]
        relocation_families = {
            checker._typescript_reference_relocation_family(identity) for identity in identities
        }
        hybrid_keys = checker._typescript_reference_hybrid_keys(identities)

        self.assertEqual(  # noqa: PT009
            155, len(identity_references), "ds5_c21d_identity_reference_drift"
        )
        self.assertEqual(  # noqa: PT009
            128, len(distinct_references), "ds5_c21d_distinct_identity_drift"
        )
        self.assertEqual(  # noqa: PT009
            107, len(relocation_families), "ds5_c21d_relocation_family_drift"
        )
        self.assertEqual(  # noqa: PT009
            128, len(set(hybrid_keys)), "ds5_c21d_hybrid_identity_merge"
        )

    def test_def21_additive_role_preserves_all_155_ds5_identity_bytes(self) -> None:
        """Pin the ordered legacy identity byte sequence across additive role changes."""
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        identity_references = [
            reference
            for reference in DS5LineAddressCensusTests._live_references(data)
            if "#ts-identity=" in reference
        ]
        encoded = json.dumps(
            identity_references,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        assert len(identity_references) == 155  # noqa: S101
        assert hashlib.sha256(encoded).hexdigest() == (  # noqa: S101
            "f1ac4d933af3c980190ee9ba31faae8e823d928ea651ff6d6117ec86f5fc42e2"
        )

    def test_c21d_multi_site_authority_sink_ignores_navigation_only_changes(self) -> None:
        """Keep semantic authority membership binding while ignoring nested navigation order."""
        finding_id = "authority-presentation-badge-compound-decision-grade"
        expected_red = f"authority_presentation_debt_drift:{finding_id}:authority_sink"
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))

        def authority_row(document: dict[str, object]) -> dict[str, object]:
            return next(
                row
                for row in document["supplemental_findings"]
                if row["finding_id"] == finding_id
            )

        original = authority_row(data)
        original_sink = original["authority_sink"]
        self.assertGreater(len(original_sink["consumer_sites"]), 1)  # noqa: PT009

        navigation_only = copy.deepcopy(data)
        navigation_sink = authority_row(navigation_only)["authority_sink"]
        navigation_sink["component_declaration"]["line"] += 100
        navigation_sink["consumer_sites"].reverse()
        for receipt in navigation_sink["consumer_sites"]:
            receipt["line"] += 100
        self.assertEqual(  # noqa: PT009
            [],
            checker._authority_presentation_errors(navigation_only, live_probes=False),
        )

        def assert_authority_sink_red(mutate: object) -> None:
            mutation = copy.deepcopy(data)
            mutate(authority_row(mutation)["authority_sink"])
            self.assertIn(  # noqa: PT009
                expected_red,
                checker._authority_presentation_errors(mutation, live_probes=False),
            )

        assert_authority_sink_red(
            lambda sink: sink["consumer_sites"][0].__setitem__(
                "path", "apps/runtime-dashboard/src/changed.tsx"
            )
        )
        assert_authority_sink_red(
            lambda sink: sink["consumer_sites"][0].__setitem__(
                "site_sha256", "sha256:" + "0" * 64
            )
        )
        assert_authority_sink_red(lambda sink: sink["consumer_sites"].pop())
        assert_authority_sink_red(
            lambda sink: sink.__setitem__("consumer_count", sink["consumer_count"] + 1)
        )
        assert_authority_sink_red(
            lambda sink: sink["consumer_sites"].append(copy.deepcopy(sink["consumer_sites"][0]))
        )

    def test_c21d_debt_group_membership_uses_identity_not_site_line(self) -> None:
        """A moved debt site retains its group through its frozen hybrid key."""
        group_id = "badge-review-required-aggregate"
        key = "a" * 64
        original = {"path": "apps/runtime-dashboard/src/example.tsx", "line": 10}
        moved = {"path": original["path"], "line": 200}

        def grouped(site: dict[str, object]) -> dict[str, list[object]]:
            location = (str(site["path"]), int(site["line"]))
            return checker._authority_badge_sites_by_debt_group(
                {"badgeSites": [site]},
                classifications={key: f"debt:{group_id}"},
                live_key_by_location={location: key},
            )

        self.assertEqual([original], grouped(original)[group_id])  # noqa: PT009
        self.assertEqual([moved], grouped(moved)[group_id])  # noqa: PT009

    def test_real_prop_declaration_and_use_move_but_reject_rewrite(self) -> None:
        """Configured prop declaration/use identities ignore navigation lines only."""
        descriptor_id = "prop-segmented-control-tone"
        specification = checker.AUTHORITY_PROP_CLASSIFICATIONS[descriptor_id]
        live_fact = next(
            fact
            for fact in checker._authority_presentation_scan()["authorityPropCensus"]
            if fact["descriptorId"] == descriptor_id
        )
        declaration_path = specification["component_declaration_path"]
        declaration_source = (checker.REPO_ROOT / declaration_path).read_text(
            encoding="utf-8"
        )
        declaration = checker._typescript_reference_identity(
            {declaration_path: declaration_source},
            source_path=declaration_path,
            role="type_property",
            discriminator="SegmentedControlProps.tone",
            navigation_hint=live_fact["propDeclarationLine"],
        )
        declaration_digest = checker._typescript_reference_hybrid_keys([declaration])[0]
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

        use_path = specification["consumer_paths"][0]
        live_use = next(
            site for site in live_fact["consumerSites"] if site["path"] == use_path
        )
        use_source = (checker.REPO_ROOT / use_path).read_text(encoding="utf-8")
        use = checker._typescript_reference_identity(
            {use_path: use_source},
            source_path=use_path,
            role="jsx_attribute",
            discriminator="tone",
            navigation_hint=live_use["line"],
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
        self.assertEqual(5, len(descriptor_references))


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

        self.assertEqual(261, len(references), "ds5_line_address_total_reference_drift")
        self.assertEqual(12, len(line_references), "ds5_line_address_line_reference_drift")
        self.assertEqual(
            10,
            len({self._LINE_REFERENCE_RE.match(reference).group(1) for reference in line_references}),
            "ds5_line_address_line_file_drift",
        )
        self.assertEqual(
            {"TSX": (0, 0), "TS": (6, 4), "PY": (4, 4), "JSON": (0, 0), "MD": (2, 2), "TOML": (0, 0)},
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
            12,
            len(navigation_references),
            "ds5_line_address_navigation_reference_drift",
        )
        self.assertEqual(
            5,
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
            12,
            len(descriptor_evidence_line_references),
            "ds5_line_address_descriptor_evidence_line_drift",
        )
        identity_references = [reference for reference in references if "#ts-identity=" in reference]
        self.assertEqual(155, len(identity_references), "ds5_c21b_identity_reference_drift")
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
            155,
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
        self.assertEqual(9, len(descriptor_identities), "ds5_c21b_descriptor_identity_drift")
        structured_descriptor_identities = [
            reference
            for finding in data["supplemental_findings"]
            if "authority_sink" not in finding
            for reference in finding["evidence_refs"]
            if "#structured-identity=" in reference
        ]
        self.assertEqual(
            5,
            len(structured_descriptor_identities),
            "ds5_c21c_descriptor_identity_drift",
        )
        self.assertEqual(
            set(checker._C21C_FROZEN_STRUCTURED_IDENTITIES.values()),
            set(structured_descriptor_identities),
            "ds5_c21c_descriptor_identity_set_drift",
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
            (28, 118, 9),
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
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        errors = checker.validate_register(data, live_probes=True, report_parity=False)
        probe_suffix = "census-browser-signing-protected-live:reference_count"
        self.assertEqual(
            [],
            [error for error in errors if error.endswith(probe_suffix)],
        )

    def test_c21b_protected_probe_retains_hybrid_identity_multiplicity(self) -> None:
        """A duplicated protected construct remains drift even when its content relocates."""
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        source_path = "apps/runtime-dashboard/src/features/runs/route.tsx"
        target_path = checker.REPO_ROOT / source_path
        original = target_path.read_text(encoding="utf-8")
        duplicated = (
            original
            + "\nexport const c19DuplicateProtectedRoutes = [\n"
            + '  "public/decisions/:signedId",\n'
            + '  "public/decisions/:signedId",\n'
            + "] as const;\n"
        )
        original_read_text = Path.read_text

        def read_text_override(path: Path, *args: object, **kwargs: object) -> str:
            if path == target_path:
                return duplicated
            return original_read_text(path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", new=read_text_override):
            errors = checker.validate_register(
                data,
                live_probes=True,
                report_parity=False,
            )

        probe_suffix = "census-browser-signing-protected-live:reference_count"
        self.assertIn(
            "census_observation_drift:" + probe_suffix,
            errors,
        )
        self.assertIn(
            "census_expected_count_drift:" + probe_suffix,
            errors,
        )

    def test_c21b_probe_mode_preserves_legacy_and_fails_closed_on_invalid_modes(self) -> None:
        """Legacy equality stays exact while mixed and unmappable identity probes fail closed."""
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        census = next(
            row
            for row in data["reference_censuses"]
            if row["census_id"] == "census-browser-signing-protected-live"
        )
        identity_reference = census["probes"][0]["observed_refs"][0]

        self.assertEqual(
            (True, None),
            checker._probe_observation_matches_stored_mode(
                ["apps/runtime-dashboard/src/example.ts:1"],
                ["apps/runtime-dashboard/src/example.ts:1"],
            ),
        )
        self.assertEqual(
            (False, None),
            checker._probe_observation_matches_stored_mode(
                ["apps/runtime-dashboard/src/example.ts:1"],
                ["apps/runtime-dashboard/src/example.ts:2"],
            ),
        )
        self.assertEqual(
            (None, "census_identity_mode_mixed"),
            checker._probe_observation_matches_stored_mode(
                [identity_reference, "apps/runtime-dashboard/src/example.ts:1"],
                ["apps/runtime-dashboard/src/example.ts:1"],
            ),
        )
        self.assertEqual(
            (
                None,
                "census_identity_observation_unmappable:README.md:1",
            ),
            checker._probe_observation_matches_stored_mode(
                [identity_reference],
                ["README.md:1"],
            ),
        )

    def test_c21b_real_gate_ignores_moved_construct_and_rejects_rename(self) -> None:
        """The governed gate binds the migrated construct identity, never its line."""
        data = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))
        source_path = "apps/runtime-dashboard/src/api/hooks/useAuthMe.ts"
        stored_references = [
            reference
            for reference in self._live_references(data)
            if reference.startswith(f"{source_path}#ts-identity=")
        ]
        self.assertEqual(1, len(stored_references))
        stored_reference = stored_references[0]

        target_path = checker.REPO_ROOT / source_path
        original = target_path.read_text(encoding="utf-8")
        block = """async function fetchAuthMe(): Promise<AuthMePayload> {
  const response = await authAwareRuntimeFetch(
    new Request(buildRuntimeApiUrl("/api/v1/auth/me"), {
      headers: {
        accept: "application/json",
      },
    }),
  );
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : null;

  if (!response.ok || !payload) {
    throw createRuntimeApiError(
      response,
      payload,
      "Failed to load auth principal",
    );
  }

  return authMeSchema.parse(payload);
}
"""
        self.assertEqual(1, original.count(block))
        without_block = original.replace(block, "", 1)
        insertion = without_block.index("export const FALLBACK_AUTH_ME")
        moved = without_block[:insertion] + block + "\n" + without_block[insertion:]
        renamed = moved.replace(
            "fetchAuthMe",
            "fetchCurrentAuthMe",
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
        """The governed writer leaves only the 12 declared navigation lines."""
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
        self.assertEqual(5, len(structured))
        self.assertEqual(12, len(remaining_lines))

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
        self.assertEqual(2, len(stored_references))
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
