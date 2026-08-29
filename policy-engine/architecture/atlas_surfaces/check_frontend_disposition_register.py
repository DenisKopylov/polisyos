"""Validate and seed the Atlas DS19 frontend disposition register.

The register is a projection over the DS1 readiness ledger and DS2 adoption
ledger.  This checker recomputes those joins, validates the strict schema, and
executes live filesystem/reference probes for every terminal deletion or
rebound claim.  Stored counts and empty arrays are never accepted as proof.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import posixpath
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import unittest
from collections import Counter, defaultdict
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:  # pragma: no cover - fail-closed operator path
    raise SystemExit(
        "jsonschema>=4.25 is required; run this checker from the repository "
        "toolchain environment"
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[2]
ATLAS_DIR = REPO_ROOT / "architecture/atlas_surfaces"
REGISTER_PATH = ATLAS_DIR / "frontend-disposition-register.json"
SCHEMA_PATH = ATLAS_DIR / "frontend-disposition-register.schema.json"
DS1_PATH = ATLAS_DIR / "live-application-readiness-ledger.json"
DS2_PATH = ATLAS_DIR / "atlas-v15-adoption-ledger.json"
BASELINE_PATH = ATLAS_DIR / "frontend-baseline-debt-manifest.json"
BASELINE_SCHEMA_PATH = ATLAS_DIR / "frontend-baseline-debt.schema.json"
REPORT_PATH = REPO_ROOT / "docs/reference/frontend/atlas-frontend-disposition-register.md"
AUDIT_PATH = REPO_ROOT / "docs/reference/frontend/atlas-live-application-audit.md"
STATUS_CHECKER_PATH = ATLAS_DIR / "check_status_retirement_inventory.py"
STATUS_INVENTORY_PATH = ATLAS_DIR / "status-retirement-inventory.json"
DS18_TIME_SEMANTICS_SCANNER_REF = (
    "architecture/atlas_surfaces/decision_time_semantics_scan.mjs"
)
DS18_TIME_SEMANTICS_SCANNER_PATH = REPO_ROOT / DS18_TIME_SEMANTICS_SCANNER_REF
DS18_TIME_SEMANTICS_SCHEMA_ID = (
    "polisyos.atlas.ds18-time-semantics-coverage.v1"
)
DS18_TIME_SEMANTICS_REVIEWER = "DS18-C06-independent-root-reconciliation"
DS18_TIME_SEMANTICS_LANDING_RULE = (
    "the slice landing a post-freeze production render/export root owns its "
    "fresh file/root receipt, independent classification, and behavioral proof"
)
DS18_TIME_SEMANTICS_BEHAVIOR_TESTS = {
    "apps/runtime-dashboard/src/features/artifacts/bureaucratic/export/export-html.ts": [
        "apps/runtime-dashboard/src/features/artifacts/bureaucratic/ast/"
        "bureaucratic-document-ast.test.ts",
    ],
    "apps/runtime-dashboard/src/features/artifacts/bureaucratic/renderers/shared/"
    "BaseBureaucraticRenderer.tsx": [
        "apps/runtime-dashboard/src/features/artifacts/bureaucratic/renderers/shared/"
        "BaseBureaucraticRenderer.test.tsx",
        "apps/runtime-dashboard/src/features/artifacts/bureaucratic/ast/"
        "bureaucratic-document-ast.test.ts",
    ],
    "apps/runtime-dashboard/src/features/artifacts/bureaucratic/renderers/shared/"
    "BureaucraticHeader.tsx": [
        "apps/runtime-dashboard/src/features/artifacts/bureaucratic/ast/"
        "bureaucratic-document-ast.test.ts",
    ],
    "apps/runtime-dashboard/src/features/export/social/EmailSummary.tsx": [
        "apps/runtime-dashboard/src/features/export/social/OGCard.test.tsx",
    ],
    "apps/runtime-dashboard/src/features/export/social/OGCard.tsx": [
        "apps/runtime-dashboard/src/features/export/social/OGCard.test.tsx",
    ],
    "apps/runtime-dashboard/src/features/export/social/generate-og.ts": [
        "apps/runtime-dashboard/src/features/export/social/OGCard.test.tsx",
    ],
    "apps/runtime-dashboard/src/features/runs/components/EpochStalenessView.tsx": [
        "apps/runtime-dashboard/src/features/runs/components/"
        "EpochStalenessView.test.tsx",
    ],
    "apps/runtime-dashboard/src/features/runs/components/PublicationPacketPanel.tsx": [
        "apps/runtime-dashboard/src/features/runs/components/"
        "PublicationPacketPanel.test.tsx",
    ],
    "apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.tsx": [
        "apps/runtime-dashboard/src/features/runs/routes/"
        "PublicDecisionViewerPage.test.tsx",
    ],
    "apps/runtime-dashboard/src/features/runs/routes/RunComparePage.tsx": [
        "apps/runtime-dashboard/src/features/runs/routes/runDetailSurfaces.test.tsx",
    ],
    "apps/runtime-dashboard/src/features/runs/routes/RunDeckPage.tsx": [
        "apps/runtime-dashboard/src/features/runs/routes/runDetailSurfaces.test.tsx",
    ],
    "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx": [
        "apps/runtime-dashboard/src/features/runs/routes/runDetailSurfaces.test.tsx",
    ],
    "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx": [
        "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.test.tsx",
        "apps/runtime-dashboard/src/features/runs/routes/runDetailSurfaces.test.tsx",
    ],
    "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx": [
        "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.test.tsx",
    ],
    "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.tsx": [
        "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.test.tsx",
    ],
    "apps/runtime-dashboard/src/shared/export/printExport.ts": [
        "apps/runtime-dashboard/src/shared/export/printExport.test.ts",
    ],
}
DS18_TIME_SEMANTICS_STRICT_PROJECTION_FILES = {
    "apps/runtime-dashboard/src/features/artifacts/bureaucratic/export/export-html.ts",
    "apps/runtime-dashboard/src/features/export/social/EmailSummary.tsx",
    "apps/runtime-dashboard/src/features/export/social/OGCard.tsx",
    "apps/runtime-dashboard/src/features/export/social/generate-og.ts",
}
DS18_TIME_SEMANTICS_DIRECT_FILES = {
    "apps/runtime-dashboard/src/features/artifacts/bureaucratic/renderers/shared/"
    "BureaucraticHeader.tsx",
    "apps/runtime-dashboard/src/features/runs/components/EpochStalenessView.tsx",
    "apps/runtime-dashboard/src/features/runs/components/PublicationPacketPanel.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunComparePage.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunDeckPage.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx",
    "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.tsx",
}
DS18_TIME_SEMANTICS_CROSS_FILE_INHERITANCE = {
    "apps/runtime-dashboard/src/features/artifacts/bureaucratic/renderers/shared/"
    "BaseBureaucraticRenderer.tsx": (
        "apps/runtime-dashboard/src/features/artifacts/bureaucratic/renderers/shared/"
        "BureaucraticHeader.tsx"
    ),
    "apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.tsx": (
        "apps/runtime-dashboard/src/features/runs/components/PublicationPacketPanel.tsx"
    ),
    "apps/runtime-dashboard/src/shared/export/printExport.ts": (
        "apps/runtime-dashboard/src/features/artifacts/bureaucratic/renderers/shared/"
        "BureaucraticHeader.tsx"
    ),
}

_STATUS_SPEC = importlib.util.spec_from_file_location(
    "frontend_disposition_status_checker", STATUS_CHECKER_PATH
)
if _STATUS_SPEC is None or _STATUS_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"Unable to import status checker from {STATUS_CHECKER_PATH}")
status_checker = importlib.util.module_from_spec(_STATUS_SPEC)
_STATUS_SPEC.loader.exec_module(status_checker)

LINT_ORIGIN_COUNT = 75
LINT_ORIGIN_FILE_COUNT = 22
LINT_ORIGIN_DIAGNOSTIC_SHA256 = (
    "3a0af02a1ba643962e83096bdcddc46dd5a637f4c4060c0a7309279f259e1648"
)
LINT_ORIGIN_IDENTITY_SHA256 = (
    "1b22f061e6b5cf61bc0f085c9927ccb5e9e899351d242503957e212f853e5830"
)
LINT_ORIGIN_RAW_RECEIPT_SHA256 = (
    "b5398177d4b6059ff4770d1bbc37d98e1879d0f17a81b8c73dac0bb504523ebb"
)
LINT_ORIGIN_RULE_SHA256 = (
    "e0014bd68cdd629307dbc1fad99c41812d6a082486cd558d48ee10648f5802b6"
)
LINT_ORIGIN_CONFIG_SHA256 = (
    "6653eb0a7475ade10b933623d0d073045731a9ecd48ae202f3b5912f5e20d4e4"
)
ARCHITECTURE_ORIGIN_COUNT = 36
ARCHITECTURE_ORIGIN_FILE_COUNT = 28
ARCHITECTURE_ORIGIN_IDENTITY_SHA256 = (
    "4c803817e489b2194e7967d2c24988b87bc56b9f4a7e09ac542a9582f25a5588"
)
ARCHITECTURE_ORIGIN_PRODUCER_SHA256 = (
    "e4dfa233f2e7c504a585688c8dbf976a9cd60c3e1baa7eb5c4898f2749cf7e98"
)
ARCHITECTURE_IDENTITY_FIELDS = (
    "source_path",
    "source_content_sha256",
    "line",
    "specifier",
    "resolved_target_path",
    "rule_id",
    "message",
)
RESOLUTION_REFERENCE_ROLES = (
    ("implementation_refs", "implementation"),
    ("consumer_refs", "consumer"),
    ("closure_test_ref", "closure_test"),
)

DECISION_DATE = "2026-07-17"
REGISTER_AS_OF = "2026-07-17T10:30:00+03:00"
REPAIR_COMMIT = "d01eaa572"
C03_REPAIR_COMMIT = "97d0c620836a3e6d33c347a1f7f563aaa9177d0c"
C03_OPEN_VITEST_SHA256 = (
    "b84ae4ba91378281c93df635f6a10079f472c96ad4c46263ebc615cfbecff0ff"
)
C03_RESOLVED_VITEST_SHA256 = (
    "eced13ccb15f90b298eb5a8320821266d2f7a1665c3f9d066775c41c144efc26"
)
C03_RECEIPT_SOURCE_SHA256 = {
    "docs/plans/active/atlas-slices/DS6-evidence-workflow.md": (
        "8339ef3b2a4c12220e0e205cb66fd5626fe1e81eebdf9cec3aafb7861c34cdad"
    ),
    "docs/plans/active/atlas-slices/DS6-evidence-workflow-journal.md": (
        "70bd0986b2b1c1d78e2e9e7e507d5f3f592ede12ccf15b27705d0da24a472eae"
    ),
}
C04_RENDERED_CONTRAST_SOURCE_REF = (
    "apps/runtime-dashboard/src/test/a11y/opaqueBackgroundContrast.ts"
)
C04_RENDERED_CONTRAST_SOURCE_PATH = REPO_ROOT / C04_RENDERED_CONTRAST_SOURCE_REF
C04_RENDERED_CONTRAST_EVIDENCE_REFS = [
    C04_RENDERED_CONTRAST_SOURCE_REF,
    "apps/runtime-dashboard/src/test/a11y/opaqueBackgroundContrast.test.ts",
    "apps/runtime-dashboard/src/test/a11y/OpaqueBackgroundContrast.stories.tsx",
]
C04_RENDERED_CONTRAST_REGISTRY_SHA256 = (
    "5f69573f7c1cbb27665d0e7696901f194a51a16ca55f6a827095fd691d761177"
)
C04_RENDERED_CONTRAST_OWNER_AST_SHA256 = (
    "d455a84a63b3fbcb1e890d913d3dad87e6abe47a69a593b4d7575f0afc743eba"
)
C04_RENDERED_CONTRAST_CLUSTER_COUNTS = {
    "C01": 1,
    "C06": 2,
    "C09": 1,
    "C14": 3,
}
C06_C04_ADMISSION_COMMIT = "39a19c078066dc8326d81f9bee1746144c52f573"
C06_C16_ENTRY_REVISION = "41a2020d5c2097c30c94807737ba6d3a80323d2e"
C06_C16_SOURCE_DELTA_SHA256 = (
    "800225190d7a47f68b585db206d6b634bd1c7787ab27bb9c5b8e8e1f5fc2bf8a"
)
C06_CONTRAST_RAW_RECEIPT_SHA256 = (
    "a608e9b606e50b75bef602136e0f9b0c47406dfedf0f68888b792b781e99eafa"
)
C06_CONTRAST_EVIDENCE_SHA256 = {
    C04_RENDERED_CONTRAST_SOURCE_REF: (
        "c54524c59102c38e02eafdf6cc690ca8896dd1a0262b243138f71e271aa0d225"
    ),
    "apps/runtime-dashboard/src/test/a11y/opaqueBackgroundContrast.test.ts": (
        "7659dac8e09ea2aa51876fda6358d543af45bf16819ac4a4ecb66db4168ebda3"
    ),
    "apps/runtime-dashboard/src/test/a11y/OpaqueBackgroundContrast.stories.tsx": (
        "681ca884a66d00bc5442906abecf30778838e228f2a94ecb446f59942b3d7fdc"
    ),
}
C06_CONTRAST_CURRENT_EVIDENCE_SHA256 = {
    C04_RENDERED_CONTRAST_SOURCE_REF: (
        "c54524c59102c38e02eafdf6cc690ca8896dd1a0262b243138f71e271aa0d225"
    ),
    "apps/runtime-dashboard/src/test/a11y/opaqueBackgroundContrast.test.ts": (
        "7659dac8e09ea2aa51876fda6358d543af45bf16819ac4a4ecb66db4168ebda3"
    ),
    "apps/runtime-dashboard/src/test/a11y/OpaqueBackgroundContrast.stories.tsx": (
        "805007c4ccefc4fb9ea682afc894ac8765dcbc9fba82e7bc13ce582596e56cbf"
    ),
}
C06_RENDERED_CONTRAST_FINDING_ID = (
    "baseline-test-a11y-rendered-contrast-incomplete-debt"
)
C13_RECEIPT_START = "<!-- DS6-C13-INDEPENDENT-PRINT-RECEIPT:START -->"
C13_RECEIPT_END = "<!-- DS6-C13-INDEPENDENT-PRINT-RECEIPT:END -->"
C13_VERIFIED_REVISION = "0440f0a8d6b64c254c37b64144461e5091e2b1db"
C13_REPAIR_COMMIT = "69aca1e25921e145fecdf57eac5a73f638f11db4"
C13_EVIDENCE_REVISION = "5255eaf4ef683d964b0a73a277751f8b9873ab41"
C13_RECEIPT_SHA256 = "bae570619054115e08d81fa04044869e19b06f4281249d3ec5b677addd6cc854"
C13_PRINT_ROOT_ID = "adjacent-print-export"
C13_PRINT_SUCCESSOR_ID = "run-report-paper-projection"
C13_TEST_TITLES = [
    "semantic DOM closes overview and report paper egress",
    "PDF keeps every page A4 and admitted growth adds pages",
    "bounded identity A4 print",
]
C13_SOURCE_REFS = [
    "apps/runtime-dashboard/src/styles/print.css",
    "apps/runtime-dashboard/src/features/runs/components/AmbientTelemetryHud.tsx",
    "apps/runtime-dashboard/src/features/runs/components/OperatorCraftPanel.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.parity.test.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.test.tsx",
    "apps/runtime-dashboard/src/features/runs/route.tsx",
    "apps/runtime-dashboard/e2e/helpers/pdfGeometry.ts",
    "apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts",
    "apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/"
    "run-report-identity-a4-print-chromium-darwin.png",
]
C13_ENVIRONMENT_PRODUCER_REF = (
    "architecture/atlas_surfaces/capture_c13_execution_environment.mjs"
)
C13_PRINT_SUCCESSOR_REFS = [
    "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx",
    "apps/runtime-dashboard/src/features/runs/route.tsx",
    "apps/runtime-dashboard/src/styles/print.css",
    "apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts",
    "apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/run-report-identity-a4-print-chromium-darwin.png",
]
C13_PRINT_OPEN_RATIONALE = (
    "Reason: C19b real-browser verification exposes run-detail-a4-print as an "
    "open product regression: the global a[href]::after print rules emit the "
    "full long public-decision URL into the report, overlap content, and prevent "
    "a stable A4 capture. DS8 owns the product repair; DS6 owns independent "
    "visual and semantic verification. Closure signal: no generated link URL "
    "overlaps the report and two consecutive no-update real-browser A4 captures "
    "are stable; until then the run-detail expectation remains unmodified and "
    "may not count green."
)
C13_PRINT_RATIONALE = (
    "DS8-A repaired the run-report paper projection at 69aca1e25; DS6-C13 "
    "independently recomputed the complete semantic egress predicate and two "
    "separate zero-retry, no-writer Chromium captures at 0440f0a8d. The "
    "snapshot stayed 26cca8a75e61cfcf across all three receipts, both PDFs "
    "were portrait A4 within 0.5 pt at 5 and 30 pages, admitted growth added "
    "pages, and the font-ready bounded identity matched. This strangles only "
    "the run-detail print predecessor; the broader print/PNG/CSV/JSON/server "
    "unit remains rebind_pending, and DS8/team-design ownership is unchanged."
)
V4_COUNTERPART_RE = re.compile(r"\[v4_counterpart=([^;\]]+)")
NEGATIVE_ID_RE = re.compile(r"`(DS1-N0(?:0[1-9]|1[0-9]|2[0-3]))`")

COLLABORATION_IDS = {
    "feature-collaboration",
    "raw-fetch-collab-activity",
    "raw-fetch-collab-comments-get",
    "raw-fetch-collab-comment-post",
    "raw-fetch-collab-resolve",
    "status-collaboration-session",
    "transport-rest-collaboration",
    "transport-ws-collaboration",
}
DELETE_ROOT_IDS = COLLABORATION_IDS | {
    "feature-onboarding-orphan",
    "route-home-clerk-duplicate",
    "feature-layout-empty",
    "worker-data-transform",
    "worker-dag-layout",
    "worker-json-parse",
    "cache-whatif-scenarios",
}

WIRE_OPERATION_RATIONALES = {
    "api-op-get-artifact-batch": "Reuse the existing typed batch producer for governed artifact inspection and packet conventions.",
    "api-op-download-artifact-content": "Reuse existing artifact addressing for governed retrieval rather than creating a second export path.",
    "api-op-export-bureaucratic-artifact": "Reuse the existing packet export/render producer instead of adding parallel export ownership.",
    "api-op-list-binding-profiles": "Expose existing registry-derived binding-profile discovery through the DS3 waist.",
    "api-op-get-packet-decision-validity": "Adopt the existing packet-validity read projection through the typed DS3 client.",
    "api-op-publish-decision-validity-event": "Adopt the live-only, principal-bound validity action through the governed DS3 client.",
    "api-op-get-run-decision-validity": "Adopt the existing run-validity inspection projection through the DS3 waist.",
    "api-op-evaluate-run-feedback": "Adopt governed review-effectiveness evaluation and its event trail through DS3.",
    "api-op-reissue-run": "Adopt the principal-bound reissue action through the generated DS3 contract.",
    "api-op-get-fabric-run-replay": "Reuse the existing replay producer for version-pinned inspection.",
    "api-op-get-fabric-source-scorecards": "Reuse the existing source-scorecard producer through one generated client.",
    "api-op-create-run-production-approval": "Adopt and harden the existing approval endpoint through the governed DS3 contract.",
    "api-op-create-run-scenario": "Use the server-backed scenario lifecycle that survives deletion of the local WhatIf branch.",
}

RETIRE_OPERATION_RATIONALES = {
    "api-op-analyze-attractors": "No accepted Atlas consumer exists; endpoint presence must not manufacture an analysis UI.",
    "api-op-persist-basin-map": "No named surface or action-authority contract consumes this persistence operation.",
    "api-op-persist-continuation-branch": "No accepted Atlas surface consumes this persistence operation.",
    "api-op-analyze-lyapunov-diagnostics": "Keep this scientific diagnostic server-only until a governed projection is specified.",
    "api-op-get-attractor-analysis": "The read half of this analysis workflow has no independently admitted consumer.",
    "api-op-get-analysis-basin-map": "The read half of this basin workflow has no admitted frontend consumer.",
    "api-op-get-analysis-continuation-branch": "The read half of this continuation workflow has no admitted frontend consumer.",
    "api-op-estimate-causal-frontier-sae": "This computation is not the DS7 acquisition frontier and has no named consumer.",
    "api-op-list-control-outbox": "Internal delivery substrate is not a product transparency surface.",
    "api-op-list-control-workers": "Internal worker-lease state is runtime infrastructure, not product navigation.",
    "api-op-get-run-compare": "The debug projection lacks a governed product contract and must not become UI authority.",
    "api-op-get-run-equilibria": "The debug diagnostic has no named consumer or governed product projection.",
    "api-op-get-run-feedback": "The debug read is not the governed review-effectiveness projection.",
    "api-op-analyze-fabric-impact": "No named consumer exists; adopting it would create a parallel analytical owner.",
    "api-op-get-fabric-quality-batch": "No accepted evidence projection names this batch as a consumer dependency.",
    "api-op-get-fabric-trust-batch": "A trust projection contract is required before frontend adoption.",
    "api-op-compute-mobility-bounds": "This domain-specific computation has no admitted universal Atlas surface.",
    "api-op-estimate-mobility": "This domain-specific computation has no admitted frontend surface.",
    "api-op-get-mobility-report": "The mobility report family has no named Atlas consumer.",
    "api-op-get-mobility-report-bounds": "The mobility report detail has no named Atlas consumer.",
    "api-op-get-mobility-report-diagnostics": "The mobility diagnostic has no named Atlas consumer.",
    "api-op-get-runs-batch": "Current run list/detail paths cover admitted surfaces; avoid a second read owner.",
    "api-op-health": "The root health probe is deployment infrastructure; the dashboard already uses governed /api/v1/health.",
    "api-op-ready": "Deployment readiness is not a product-readiness claim or browser surface.",
}

FLAG_DECISIONS = {
    "flag-enable-causal-graph": (
        "wire_disposition",
        "The graph is live outside its declared gate; DS5 must wire one whole-surface exposure gate.",
    ),
    "flag-enable-collaboration": (
        "retire_disposition",
        "The orphan collaboration surface is deleted, so its unused flag cannot remain false continuity.",
    ),
    "flag-enable-command-palette": (
        "wire_disposition",
        "The live palette must consume its existing key as a genuine launch gate.",
    ),
    "flag-enable-what-if-analysis": (
        "wire_disposition",
        "The surviving server-backed workbench needs one real whole-surface exposure gate.",
    ),
}

SCAN_ROOTS = [
    "apps/runtime-dashboard/src",
    "apps/runtime-dashboard/e2e",
    "apps/runtime-dashboard/.storybook",
    "apps/runtime-dashboard/scripts",
    "apps/runtime-dashboard/package.json",
    "packages",
]

UI_PRIMITIVES_ROOT_ID = "ui-primitives-root"
UI_PRIMITIVES_CENSUS_ID = "census-ds4-c03b-dormant-primitives"
UI_PRIMITIVES_PRE_DELETION_COMMIT = "caa1ee6e3ab49d559b19dbeeda6308c3598e7183"
UI_PRIMITIVES_RESURRECTION_RULE = (
    "recreate_in_atlas_ui_only_with_a_real_production_consumer_"
    "never_restore_in_the_app_tree"
)
UI_PRIMITIVES_CHECKED_IMPORT_FORMS = {
    "direct",
    "barrel",
    "namespace",
    "relative",
    "dynamic",
    "composition",
}
UI_PRIMITIVES_PACKAGE_MIGRATED = {
    "AsyncSection",
    "Badge",
    "Button",
    "Card",
    "Checkbox",
    "Command",
    "Dialog",
    "EmptyState",
    "Icon",
    "Input",
    "Label",
    "Popover",
    "Radio",
    "SegmentedControl",
    "Select",
    "Skeleton",
    "Slider",
    "Switch",
    "Text",
    "Textarea",
    "ToggleButton",
    "Tooltip",
}
ATLAS_UI_DEFINE_ONCE_PRIMITIVES = {
    "AuthorityBadge",
    "EnvelopeChip",
    "EvidenceLink",
}
ATLAS_UI_SUPPORT_MODULES = {"evidenceTypes"}
ATLAS_UI_OTHER_EXPORTS = {"JsonPreview", "VirtualList", "VirtualTable"}
UI_PRIMITIVES_DASHBOARD_REBOUND = {"ApiErrorAlert", "ProvenanceStrip"}
UI_PRIMITIVES_MEMBER_RULES = {
    "DropdownMenu": {
        "disposition": "retire",
        "ds2_adoption_id": None,
        "governing_condition": None,
        "ledger_absence_reason": "no_exact_ds2_row",
    },
    "ScrollArea": {
        "disposition": "use_as_is",
        "ds2_adoption_id": "component-scroll-area",
        "governing_condition": (
            "Archive admission alone sunsets nothing. DS4 may remove a mapped loser "
            "only after generated/source ownership, consumer migration, drift checks, "
            "and the owning slice's DS6 evidence are complete."
        ),
        "ledger_absence_reason": None,
    },
    "Separator": {
        "disposition": "retire",
        "ds2_adoption_id": None,
        "governing_condition": None,
        "ledger_absence_reason": "no_exact_ds2_row",
    },
    "Sheet": {
        "disposition": "retire",
        "ds2_adoption_id": None,
        "governing_condition": None,
        "ledger_absence_reason": "no_exact_ds2_row",
    },
    "Tabs": {
        "disposition": "use_as_is",
        "ds2_adoption_id": "component-tabs",
        "governing_condition": (
            "Keep the mapped live v4 family as the transitional winner until DS4 "
            "routes a real consumer through one governed replacement, DS6 passes its "
            "negative/browser/accessibility evidence, and the old import path is removed."
        ),
        "ledger_absence_reason": None,
    },
}
UI_PRIMITIVES_DELETED_BLOBS = {
    "apps/runtime-dashboard/src/shared/ui/DropdownMenu.tsx": (
        "7bf4bfc423f17393ac1f8646e94d0da8b8d0c8a6"
    ),
    "apps/runtime-dashboard/src/shared/ui/DropdownMenu.a11y.test.tsx": (
        "67e09a12bef1f1fe0b996dcdbc151bc9f8ee8a33"
    ),
    "apps/runtime-dashboard/src/shared/ui/Separator.tsx": (
        "de156b91bb009e287df0e3fda6f70ae21364bd13"
    ),
    "apps/runtime-dashboard/src/shared/ui/Separator.a11y.test.tsx": (
        "1da3670349e6b31b832c1fa5ee236d58ff57eab6"
    ),
    "apps/runtime-dashboard/src/shared/ui/Sheet.tsx": (
        "c119e917a73c942e2c2b00a03b84b7c3d86b6d5e"
    ),
    "apps/runtime-dashboard/src/shared/ui/Sheet.a11y.test.tsx": (
        "5b4f8d67e39bd31869ebe9d753015fcac9fc58f1"
    ),
}
UI_PRIMITIVES_RETAINED_PATHS = {
    "apps/runtime-dashboard/src/shared/ui/ScrollArea.tsx",
    "apps/runtime-dashboard/src/shared/ui/ScrollArea.a11y.test.tsx",
    "apps/runtime-dashboard/src/shared/ui/Tabs.tsx",
    "apps/runtime-dashboard/src/shared/ui/Tabs.a11y.test.tsx",
}
UI_PRIMITIVES_BARREL = "apps/runtime-dashboard/src/shared/ui/primitives/index.ts"
ATLAS_UI_INDEX = "packages/atlas-ui/src/index.ts"
C15_ROOT_ID = "ui-compounds-root"
C15_PACKAGE_MIGRATED = {"JsonPreview", "VirtualList", "VirtualTable"}
C15_DASHBOARD_USE_AS_IS = {"DataTable", "MetricCard", "LineageGraph"}
C15_JSON_PREVIEW_ADAPTER = (
    "apps/runtime-dashboard/src/shared/ui/LocalizedJsonPreview.tsx"
)
C15_SUCCESSOR_ID = "atlas-ui-root-compounds-and-dashboard-transitional-winners"
C15_CONSUMER_REFS = [
    "packages/atlas-ui/src/index.ts",
    "packages/atlas-ui/src/compounds/JsonPreview.tsx",
    "packages/atlas-ui/src/compounds/VirtualList.tsx",
    "packages/atlas-ui/src/compounds/VirtualTable.tsx",
    "packages/atlas-ui/tests/compoundComponents.test.tsx",
    "packages/atlas-ui/tests/compoundComponents.a11y.test.tsx",
    "packages/atlas-ui/tests/oneOwner.test.ts",
    "apps/runtime-dashboard/src/features/artifacts/components/ArtifactViewerRegistry.tsx",
    "apps/runtime-dashboard/src/features/artifacts/components/ArtifactViewerRegistry.test.tsx",
    "apps/runtime-dashboard/src/features/evidence/components/DataIntelligencePanel.tsx",
    "apps/runtime-dashboard/src/features/runs/components/GovernanceReport.tsx",
    "apps/runtime-dashboard/src/features/runs/components/debug/ErrorsPanel.tsx",
    "apps/runtime-dashboard/src/features/runs/components/debug/NodeDebugPanel.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/tabs/DebugTab.tsx",
    "apps/runtime-dashboard/src/shared/ui/DataTable.tsx",
    "apps/runtime-dashboard/src/shared/ui/MetricCard.tsx",
    "apps/runtime-dashboard/src/shared/ui/LineageGraph.tsx",
    "apps/runtime-dashboard/src/shared/ui/LineageGraph.test.tsx",
    "apps/runtime-dashboard/src/shared/ui/LocalizedJsonPreview.tsx",
    "apps/runtime-dashboard/src/shared/ui/compounds/StatusTimeline.tsx",
    "apps/runtime-dashboard/src/shared/ui/sharedUiArchitecture.test.ts",
]
C15_MIXED_RATIONALE = (
    "C15 records an explicit mixed six-component receipt: JsonPreview, VirtualList, "
    "and VirtualTable are package-migrated with symbol-derived live dashboard consumers, "
    "JsonPreview translation remains app-owned through a typed labels adapter, and their "
    "dashboard owners are strangled; DataTable and MetricCard remain dashboard-owned use_as_is "
    "transitional "
    "winners until their exact DS2 sunset condition is met by DS4 consumer routing, DS6 "
    "negative/browser/accessibility evidence, and old-import removal; LineageGraph remains "
    "dashboard-owned use_as_is until a DS16 typed adapter and DS6 degraded/keyboard/table/export "
    "evidence exist, while C15 only removes its local status-to-authority color guessing. This "
    "receipt claims no DS2, DS6, or DS16 completion."
)
C16_ROOT_ID = "ui-patterns"
C16_PACKAGE_MIGRATED = {"DetailLayout", "FilterPanel"}
C16_SEARCHABLE_LIST = "SearchableList"
C16_SUCCESSOR_ID = "atlas-ui-shared-patterns-and-dashboard-searchable-list"
C16_REQUIRED_PATHS = {
    "packages/atlas-ui/src/index.ts",
    "packages/atlas-ui/src/patterns/DetailLayout.tsx",
    "packages/atlas-ui/src/patterns/FilterPanel.tsx",
    "packages/atlas-ui/tests/oneOwner.test.ts",
    "packages/atlas-ui/tests/patternComponents.a11y.test.tsx",
    "packages/atlas-ui/tests/patternComponents.test.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx",
    "apps/runtime-dashboard/src/shared/ui/patterns/Patterns.stories.tsx",
    "apps/runtime-dashboard/src/shared/ui/patterns/SearchableList.a11y.test.tsx",
    "apps/runtime-dashboard/src/shared/ui/patterns/SearchableList.test.tsx",
    "apps/runtime-dashboard/src/shared/ui/patterns/SearchableList.tsx",
    "apps/runtime-dashboard/src/shared/ui/sharedUiArchitecture.test.ts",
}
C16_RETIRED_PATHS = {
    "apps/runtime-dashboard/src/shared/ui/patterns/DetailLayout.a11y.test.tsx",
    "apps/runtime-dashboard/src/shared/ui/patterns/DetailLayout.tsx",
    "apps/runtime-dashboard/src/shared/ui/patterns/FilterPanel.a11y.test.tsx",
    "apps/runtime-dashboard/src/shared/ui/patterns/FilterPanel.tsx",
}
C16_EXPECTED_PRODUCTION_CONSUMERS = {
    "DetailLayout": {
        "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx"
    },
    "FilterPanel": {
        "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx"
    },
}
C16_CONSUMER_REFS = [
    "packages/atlas-ui/src/index.ts",
    "packages/atlas-ui/src/patterns/DetailLayout.tsx",
    "packages/atlas-ui/src/patterns/FilterPanel.tsx",
    "packages/atlas-ui/tests/patternComponents.test.tsx",
    "packages/atlas-ui/tests/patternComponents.a11y.test.tsx",
    "packages/atlas-ui/tests/oneOwner.test.ts",
    "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx",
    "apps/runtime-dashboard/src/shared/ui/patterns/SearchableList.tsx",
    "apps/runtime-dashboard/src/shared/ui/patterns/SearchableList.test.tsx",
    "apps/runtime-dashboard/src/shared/ui/patterns/SearchableList.a11y.test.tsx",
    "apps/runtime-dashboard/src/shared/ui/patterns/Patterns.stories.tsx",
    "apps/runtime-dashboard/src/shared/ui/sharedUiArchitecture.test.ts",
]
C16_FLOW_IDS = {
    "flow-audit-export",
    "flow-decision-packet-review",
    "flow-dispute-appeal",
    "flow-evidence-intake",
    "flow-failure-triage",
    "flow-long-running-jobs",
    "flow-permission-request",
}
C16_FLOW_OWNER_SLICES = ["DS5", "DS7", "DS8", "DS9", "DS12", "DS14", "DS15", "DS17"]
C16_FLOW_REASON = (
    "The flow is useful material but remains contract-only until its producer, persisted "
    "artifact, bridge, consumer, verification, and semantic negative are wired. "
    "[v4_counterpart=ui-patterns; transitional_winner=living-v4-ui-patterns; "
)
C16_FLOW_CLOSURE_SIGNAL = (
    "Revisit after the named owning slice binds the flow to runtime artifacts, lifecycle "
    "effects, a live consumer, and DS6 negative/e2e evidence."
)
C16_MIXED_RATIONALE = (
    "C16 records an exact mixed three-component receipt: DetailLayout and FilterPanel are "
    "package-migrated with direct symbol-derived production consumers and their dashboard "
    "owners are strangled; SearchableList remains the dashboard-owned use_as_is winner in "
    "consumer_missing state because it has no production consumer, and its closure signal is "
    "a real production consumer followed by a separately adjudicated owner migration. The "
    "responsive-layout DS2 rows remain unresolved until DS4 binds one breakpoint owner and "
    "DS6 supplies browser, print, touch, zoom, and data-state evidence; component-search-field "
    "and form-search-source-selection remain unclaimed until their live-consumer and DS6 "
    "conditions are met. The seven attached flow IDs remain contract_only debt owned by "
    "DS5/DS7/DS8/DS9/DS12/DS14/DS15/DS17 because producer, artifact, bridge, consumer, "
    "verification, and semantic-negative evidence are missing; closure requires each named "
    "owner to bind runtime artifacts, lifecycle effects, a live consumer, and DS6 negative/e2e "
    "evidence. This receipt claims no DS2, DS6, or product-flow completion."
)
C17_ROOT_ID = "ui-responsive"
C17_TOKEN_ROOT_ID = "ui-tokens"
C17_COMPONENTS = {"BottomSheet", "MobileNav", "PullToRefresh", "SwipeableDrawer"}
C17_HOOK_EXPORTS = {"useBreakpoint"}
C17_SUCCESSOR_ID = "dashboard-responsive-generated-breakpoint-adapter"
C17_EVIDENCE_IDS = {"responsive-shell-navigation", "token-root-responsive"}
C17_HOOK_CONSUMERS = {
    "useBreakpoint": {
        "apps/runtime-dashboard/src/features/artifacts/reading-view/hooks/useMarginNoteAnchors.ts"
    },
    "useIsMobile": {
        "apps/runtime-dashboard/src/app/layout/AppShell.tsx",
        "apps/runtime-dashboard/src/features/evidence/routes/EvidenceFabricPage.tsx",
    },
}
C17_CONSUMER_REFS = [
    "packages/atlas-ui/src/generated/tokens.ts",
    "packages/atlas-ui/tests/tokenProjectionParity.test.ts",
    "apps/runtime-dashboard/src/shared/ui/responsive/index.ts",
    "apps/runtime-dashboard/src/shared/ui/responsive/useBreakpoint.ts",
    "apps/runtime-dashboard/src/shared/ui/responsive/responsiveTokenParity.test.tsx",
    "apps/runtime-dashboard/src/shared/ui/responsive/BottomSheet.tsx",
    "apps/runtime-dashboard/src/shared/ui/responsive/BottomSheet.a11y.test.tsx",
    "apps/runtime-dashboard/src/shared/ui/responsive/MobileNav.tsx",
    "apps/runtime-dashboard/src/shared/ui/responsive/MobileNav.a11y.test.tsx",
    "apps/runtime-dashboard/src/shared/ui/responsive/PullToRefresh.tsx",
    "apps/runtime-dashboard/src/shared/ui/responsive/PullToRefresh.a11y.test.tsx",
    "apps/runtime-dashboard/src/shared/ui/responsive/SwipeableDrawer.tsx",
    "apps/runtime-dashboard/src/shared/ui/responsive/SwipeableDrawer.a11y.test.tsx",
    "apps/runtime-dashboard/src/app/layout/AppMobileNav.tsx",
    "apps/runtime-dashboard/src/app/layout/AppShell.tsx",
    "apps/runtime-dashboard/src/features/evidence/routes/EvidenceFabricPage.tsx",
    "apps/runtime-dashboard/src/features/artifacts/reading-view/hooks/useMarginNoteAnchors.ts",
]
C17_RATIONALE = (
    "C17 records an exact four-component use_as_is receipt: BottomSheet, MobileNav, "
    "PullToRefresh, and SwipeableDrawer remain dashboard-owned through the unchanged responsive "
    "barrel; the existing useBreakpoint/useIsMobile seam now consumes the generated atlas-ui "
    "breakpointProjection.runtime, with three live hook consumers and behavioral parity covering "
    "all five edges, media-query updates, useIsMobile, injected projection drift, and retained "
    "gestures. Only token-root-responsive material and responsive-shell-navigation behavior "
    "inform this bounded receipt. ui-tokens remains rebind_pending because designTokens.ts is not "
    "proven mechanically generated; responsive-breakpoint-taxonomy remains rejected; every other "
    "responsive DS2 row remains at its DS2 verdict and DS6 gate. This receipt claims no browser, "
    "print, touch-device, manual-AT, DS2, DS6, taxonomy, or component-sunset completion."
)

_TS_MODULE_FACTS_SCRIPT = r"""
import path from "node:path";
import ts from "typescript";

let raw = "";
for await (const chunk of process.stdin) raw += chunk;
const sources = JSON.parse(raw);
const dashboardRoot = process.cwd();
const repoRoot = path.resolve(dashboardRoot, "../..");
const config = ts.readConfigFile(
  path.join(dashboardRoot, "tsconfig.app.json"),
  ts.sys.readFile,
);
if (config.error) {
  throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, "\n"));
}
const parsedConfig = ts.parseJsonConfigFileContent(config.config, ts.sys, dashboardRoot);
if (parsedConfig.errors.length > 0) {
  throw new Error(ts.flattenDiagnosticMessageText(parsedConfig.errors[0].messageText, "\n"));
}
const facts = [];
const compilerOptions = {
  ...parsedConfig.options,
  jsx: ts.JsxEmit.Preserve,
  module: ts.ModuleKind.ESNext,
  noLib: true,
  noResolve: true,
  target: ts.ScriptTarget.Latest,
};
const virtualSources = new Map(Object.entries(sources));
const host = ts.createCompilerHost(compilerOptions, true);
const defaultFileExists = host.fileExists.bind(host);
const defaultReadFile = host.readFile.bind(host);
const defaultGetSourceFile = host.getSourceFile.bind(host);
host.fileExists = (fileName) => virtualSources.has(fileName) || defaultFileExists(fileName);
host.readFile = (fileName) => virtualSources.get(fileName) ?? defaultReadFile(fileName);
host.getSourceFile = (fileName, languageVersion, onError, shouldCreateNewSourceFile) => {
  const source = virtualSources.get(fileName);
  if (source !== undefined) {
    const kind = fileName.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
    return ts.createSourceFile(fileName, source, languageVersion, true, kind);
  }
  return defaultGetSourceFile(
    fileName,
    languageVersion,
    onError,
    shouldCreateNewSourceFile,
  );
};
const program = ts.createProgram({
  rootNames: [...virtualSources.keys()],
  options: compilerOptions,
  host,
});
const checker = program.getTypeChecker();

function resolvedModulePath(relativePath, specifier) {
  const resolved = ts.resolveModuleName(
    specifier,
    path.resolve(repoRoot, relativePath),
    compilerOptions,
    host,
  ).resolvedModule?.resolvedFileName;
  return resolved
    ? path.relative(repoRoot, path.resolve(resolved)).split(path.sep).join("/")
    : null;
}

for (const [path] of Object.entries(sources)) {
  const file = program.getSourceFile(path);
  if (!file) throw new Error(`Missing virtual source: ${path}`);
  const propertyUses = new Map();

  function collect(node) {
    if (ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.expression)) {
      const names = propertyUses.get(node.expression.text) ?? new Set();
      names.add(node.name.text);
      propertyUses.set(node.expression.text, names);
    } else if (
      ts.isElementAccessExpression(node) &&
      ts.isIdentifier(node.expression) &&
      ts.isStringLiteral(node.argumentExpression)
    ) {
      const names = propertyUses.get(node.expression.text) ?? new Set();
      names.add(node.argumentExpression.text);
      propertyUses.set(node.expression.text, names);
    }
    ts.forEachChild(node, collect);
  }
  collect(file);

  function line(node) {
    return file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1;
  }
  function isWithin(node, predicate) {
    let current = node.parent;
    while (current && current !== file) {
      if (predicate(current)) return true;
      current = current.parent;
    }
    return false;
  }
  function isValueIdentifierUse(node, binding, bindingSymbol) {
    if (node === binding || checker.getSymbolAtLocation(node) !== bindingSymbol) {
      return false;
    }
    if (
      isWithin(
        node,
        (ancestor) =>
          ts.isImportDeclaration(ancestor) ||
          ts.isExportDeclaration(ancestor) ||
          ts.isTypeNode(ancestor),
      )
    ) {
      return false;
    }
    return true;
  }
  function bindingHasValueUse(binding) {
    const bindingSymbol = checker.getSymbolAtLocation(binding);
    if (!bindingSymbol) return false;
    let used = false;
    function scan(node) {
      if (used) return;
      if (
        ts.isIdentifier(node) &&
        isValueIdentifierUse(node, binding, bindingSymbol)
      ) {
        used = true;
        return;
      }
      ts.forEachChild(node, scan);
    }
    scan(file);
    return used;
  }
  function bindingHasJsxElementUse(binding) {
    const bindingSymbol = checker.getSymbolAtLocation(binding);
    if (!bindingSymbol) return false;
    let used = false;
    function scan(node) {
      if (used) return;
      if (
        (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
        ts.isIdentifier(node.tagName) &&
        checker.getSymbolAtLocation(node.tagName) === bindingSymbol
      ) {
        used = true;
        return;
      }
      ts.forEachChild(node, scan);
    }
    scan(file);
    return used;
  }
  function namespaceJsxElementNames(binding) {
    const bindingSymbol = checker.getSymbolAtLocation(binding);
    if (!bindingSymbol) return [];
    const names = new Set();
    function scan(node) {
      if (
        (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
        ts.isPropertyAccessExpression(node.tagName) &&
        ts.isIdentifier(node.tagName.expression) &&
        checker.getSymbolAtLocation(node.tagName.expression) === bindingSymbol
      ) {
        names.add(node.tagName.name.text);
      }
      ts.forEachChild(node, scan);
    }
    scan(file);
    return [...names];
  }
  function bindingNames(name) {
    if (ts.isIdentifier(name)) return [name.text];
    if (ts.isObjectBindingPattern(name) || ts.isArrayBindingPattern(name)) {
      return name.elements.flatMap((element) =>
        ts.isBindingElement(element) ? bindingNames(element.name) : [],
      );
    }
    return [];
  }
  function callbackModuleNames(callback) {
    if (
      !callback ||
      (!ts.isArrowFunction(callback) && !ts.isFunctionExpression(callback)) ||
      callback.parameters.length === 0
    ) {
      return [];
    }
    const parameter = callback.parameters[0].name;
    if (ts.isObjectBindingPattern(parameter)) {
      return parameter.elements
        .filter((element) => !element.dotDotDotToken)
        .map((element) => (element.propertyName ?? element.name).text);
    }
    if (ts.isIdentifier(parameter)) {
      return [...(propertyUses.get(parameter.text) ?? [])];
    }
    return [];
  }
  function continuationNames(binding) {
    const bindingSymbol = checker.getSymbolAtLocation(binding);
    if (!bindingSymbol) return [];
    const names = new Set();
    function sameBinding(node) {
      return ts.isIdentifier(node) && checker.getSymbolAtLocation(node) === bindingSymbol;
    }
    function scan(node) {
      if (
        ts.isCallExpression(node) &&
        ts.isPropertyAccessExpression(node.expression) &&
        node.expression.name.text === "then" &&
        sameBinding(node.expression.expression)
      ) {
        for (const name of callbackModuleNames(node.arguments[0])) names.add(name);
      } else if (
        ts.isVariableDeclaration(node) &&
        node.initializer &&
        ts.isAwaitExpression(node.initializer) &&
        sameBinding(node.initializer.expression)
      ) {
        if (ts.isObjectBindingPattern(node.name)) {
          for (const element of node.name.elements) {
            if (!element.dotDotDotToken) {
              names.add((element.propertyName ?? element.name).text);
            }
          }
        } else if (ts.isIdentifier(node.name)) {
          for (const name of propertyUses.get(node.name.text) ?? []) names.add(name);
        }
      }
      ts.forEachChild(node, scan);
    }
    scan(file);
    return [...names];
  }
  function dynamicNames(call) {
    let expression = call;
    while (
      expression.parent &&
      ((ts.isAwaitExpression(expression.parent) && expression.parent.expression === expression) ||
        (ts.isParenthesizedExpression(expression.parent) &&
          expression.parent.expression === expression) ||
        (ts.isAsExpression(expression.parent) && expression.parent.expression === expression) ||
        (ts.isNonNullExpression(expression.parent) &&
          expression.parent.expression === expression))
    ) {
      expression = expression.parent;
    }
    const parent = expression.parent;
    if (
      parent &&
      ts.isPropertyAccessExpression(parent) &&
      parent.expression === expression &&
      parent.name.text === "then" &&
      ts.isCallExpression(parent.parent) &&
      parent.parent.expression === parent
    ) {
      return callbackModuleNames(parent.parent.arguments[0]);
    }
    if (parent && ts.isPropertyAccessExpression(parent) && parent.expression === expression) {
      return [parent.name.text];
    }
    if (
      parent &&
      ts.isElementAccessExpression(parent) &&
      parent.expression === expression &&
      ts.isStringLiteral(parent.argumentExpression)
    ) {
      return [parent.argumentExpression.text];
    }
    if (parent && ts.isVariableDeclaration(parent) && parent.initializer === expression) {
      if (ts.isObjectBindingPattern(parent.name)) {
        return parent.name.elements
          .filter((element) => !element.dotDotDotToken)
          .map((element) => (element.propertyName ?? element.name).text);
      }
      if (ts.isIdentifier(parent.name)) {
        return [
          ...new Set([
            ...(propertyUses.get(parent.name.text) ?? []),
            ...continuationNames(parent.name),
          ]),
        ];
      }
    }
    if (
      parent &&
      ts.isBinaryExpression(parent) &&
      parent.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
      parent.right === expression &&
      ts.isIdentifier(parent.left)
    ) {
      return [
        ...new Set([
          ...(propertyUses.get(parent.left.text) ?? []),
          ...continuationNames(parent.left),
        ]),
      ];
    }
    return [];
  }
  function visit(node) {
    if (node.parent === file) {
      if (
        (ts.isFunctionDeclaration(node) ||
          ts.isClassDeclaration(node) ||
          ts.isEnumDeclaration(node)) &&
        node.name
      ) {
        facts.push({
          path,
          kind: "owner_symbol",
          module: "",
          names: [node.name.text],
          exported_names: [node.name.text],
          namespace_usages: [],
          value_binding_used: false,
          line: line(node),
        });
      } else if (ts.isVariableStatement(node)) {
        const names = node.declarationList.declarations.flatMap((declaration) =>
          bindingNames(declaration.name),
        );
        if (names.length > 0) {
          facts.push({
            path,
            kind: "owner_symbol",
            module: "",
            names,
            exported_names: names,
            namespace_usages: [],
            value_binding_used: false,
            line: line(node),
          });
        }
      }
    }
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      const clause = node.importClause;
      facts.push({
        path,
        kind: "import_declaration",
        module: node.moduleSpecifier.text,
        resolved_module: resolvedModulePath(path, node.moduleSpecifier.text),
        names: [],
        exported_names: [],
        namespace_usages: [],
        value_binding_used: false,
        line: line(node),
      });
      if (clause && !clause.isTypeOnly) {
        const names = [];
        const usedNames = [];
        const jsxElementNames = [];
        let namespace = null;
        let namespaceUsed = false;
        let defaultUsed = false;
        if (clause.name) defaultUsed = bindingHasValueUse(clause.name);
        const bindings = clause.namedBindings;
        if (bindings && ts.isNamedImports(bindings)) {
          for (const element of bindings.elements) {
            if (!element.isTypeOnly) {
              const importedName = (element.propertyName ?? element.name).text;
              names.push(importedName);
              if (bindingHasValueUse(element.name)) usedNames.push(importedName);
              if (bindingHasJsxElementUse(element.name)) jsxElementNames.push(importedName);
            }
          }
        } else if (bindings && ts.isNamespaceImport(bindings)) {
          namespace = bindings.name.text;
          namespaceUsed = bindingHasValueUse(bindings.name);
          jsxElementNames.push(...namespaceJsxElementNames(bindings.name));
        }
        facts.push({
          path,
          kind: "static",
          module: node.moduleSpecifier.text,
          names,
          exported_names: [],
          used_names: usedNames,
          jsx_element_names: jsxElementNames,
          namespace_usages: namespace ? [...(propertyUses.get(namespace) ?? [])] : [],
          value_binding_used: defaultUsed || namespaceUsed || usedNames.length > 0,
          line: line(node),
        });
      }
    } else if (
      ts.isExportDeclaration(node) &&
      !node.isTypeOnly
    ) {
      let names = ["*"];
      let exportedNames = ["*"];
      if (node.exportClause && ts.isNamedExports(node.exportClause)) {
        const elements = node.exportClause.elements.filter((element) => !element.isTypeOnly);
        names = elements.map((element) => (element.propertyName ?? element.name).text);
        exportedNames = elements.map((element) => element.name.text);
      } else if (node.exportClause && ts.isNamespaceExport(node.exportClause)) {
        names = ["*"];
        exportedNames = [node.exportClause.name.text];
      }
      facts.push({
        path,
        kind: "export",
        module:
          node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)
            ? node.moduleSpecifier.text
            : "",
        names,
        exported_names: exportedNames,
        namespace_usages: [],
        value_binding_used: false,
        line: line(node),
      });
    } else if (
      ts.isCallExpression(node) &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0]) &&
      (node.expression.kind === ts.SyntaxKind.ImportKeyword ||
        (ts.isIdentifier(node.expression) && node.expression.text === "require"))
    ) {
      facts.push({
        path,
        kind: "dynamic",
        module: node.arguments[0].text,
        names: dynamicNames(node),
        exported_names: [],
        namespace_usages: [],
        value_binding_used: dynamicNames(node).length > 0,
        line: line(node),
      });
    }
    ts.forEachChild(node, visit);
  }
  visit(file);
}

process.stdout.write(JSON.stringify(facts));
"""

_TS_MODULE_FACTS_CACHE: dict[str, list[dict[str, Any]]] = {}

_TS_LITERAL_OBJECT_ARRAY_SCRIPT = r"""
import { createHash } from "node:crypto";
import ts from "typescript";

let raw = "";
for await (const chunk of process.stdin) raw += chunk;
const input = JSON.parse(raw);
const sourceFile = ts.createSourceFile(
  input.sourcePath,
  input.source,
  ts.ScriptTarget.Latest,
  true,
  input.sourcePath.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
);

function ownerAstSha256() {
  const canonical = ts
    .createPrinter({
      newLine: ts.NewLineKind.LineFeed,
      removeComments: false,
    })
    .printFile(sourceFile);
  return createHash("sha256").update(canonical).digest("hex");
}

function unwrapParentheses(expression) {
  let current = expression;
  while (ts.isParenthesizedExpression(current)) {
    current = current.expression;
  }
  return current;
}

function propertyName(name) {
  if (ts.isIdentifier(name) || ts.isStringLiteral(name)) return name.text;
  return null;
}

function objectRows(initializer, errors) {
  const array = unwrapParentheses(initializer);
  if (!ts.isArrayLiteralExpression(array)) {
    errors.push("initializer_not_literal_array");
    return [];
  }
  return array.elements.map((element, index) => {
    const object = unwrapParentheses(element);
    if (!ts.isObjectLiteralExpression(object)) {
      errors.push(`element_not_literal_object:${index}`);
      return {};
    }
    const row = {};
    for (const property of object.properties) {
      if (!ts.isPropertyAssignment(property)) {
        errors.push(`property_not_assignment:${index}`);
        continue;
      }
      const name = propertyName(property.name);
      const value = unwrapParentheses(property.initializer);
      if (name === null || !ts.isStringLiteral(value)) {
        errors.push(`property_not_string_literal:${index}`);
        continue;
      }
      if (Object.prototype.hasOwnProperty.call(row, name)) {
        errors.push(`duplicate_property:${index}:${name}`);
        continue;
      }
      row[name] = value.text;
    }
    return row;
  });
}

const matches = [];
const errors = sourceFile.parseDiagnostics.map((diagnostic) =>
  ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n"),
);

function hasModifier(node, kind) {
  return Boolean(node.modifiers?.some((modifier) => modifier.kind === kind));
}

function visit(node) {
  if (
    ts.isImportDeclaration(node) ||
    ts.isImportEqualsDeclaration(node) ||
    ts.isImportTypeNode(node) ||
    (ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword)
  ) {
    errors.push("runtime_owner_not_import_free");
  }
  if (ts.isExportAssignment(node)) {
    errors.push("runtime_owner_alternate_export");
  }
  if (
    ts.isIdentifier(node) &&
    ["exports", "module", "require"].includes(node.text)
  ) {
    errors.push("runtime_owner_commonjs_escape");
  }
  if (hasModifier(node, ts.SyntaxKind.DeclareKeyword)) {
    errors.push("runtime_owner_ambient_declaration");
  }
  if (
    ts.isVariableDeclaration(node) &&
    ts.isIdentifier(node.name) &&
    node.name.text === input.binding
  ) {
    const declarationList = node.parent;
    const statement = declarationList.parent;
    let assertedInitializer = node.initializer;
    while (assertedInitializer && ts.isParenthesizedExpression(assertedInitializer)) {
      assertedInitializer = assertedInitializer.expression;
    }
    const isDirectExportedConst =
      ts.isVariableDeclarationList(declarationList) &&
      declarationList.declarations.length === 1 &&
      Boolean(declarationList.flags & ts.NodeFlags.Const) &&
      ts.isVariableStatement(statement) &&
      statement.parent === sourceFile &&
      hasModifier(statement, ts.SyntaxKind.ExportKeyword) &&
      !hasModifier(statement, ts.SyntaxKind.DeclareKeyword) &&
      node.type === undefined;
    if (!isDirectExportedConst) errors.push("binding_not_direct_exported_const");
    const isConstAssertion = Boolean(
      assertedInitializer &&
        ts.isAsExpression(assertedInitializer) &&
        assertedInitializer.type.getText(sourceFile) === "const"
    );
    if (!isConstAssertion) {
      errors.push("binding_not_const_asserted");
    }
    if (!node.initializer) {
      errors.push("initializer_missing");
      matches.push([]);
    } else {
      matches.push(
        objectRows(
          isConstAssertion ? assertedInitializer.expression : node.initializer,
          errors,
        ),
      );
    }
  }
  ts.forEachChild(node, visit);
}
visit(sourceFile);

for (const statement of sourceFile.statements) {
  if (ts.isImportDeclaration(statement) || ts.isImportEqualsDeclaration(statement)) {
    errors.push("runtime_owner_not_import_free");
  }
  if (ts.isExportDeclaration(statement)) {
    if (!statement.exportClause) {
      errors.push("runtime_owner_export_star_ambiguous");
    } else if (
      ts.isNamedExports(statement.exportClause) &&
      statement.exportClause.elements.some(
        (element) =>
          element.name.text === input.binding ||
          element.propertyName?.text === input.binding,
      )
    ) {
      errors.push("runtime_owner_alternate_export");
    }
  }
  if (
    (ts.isFunctionDeclaration(statement) ||
      ts.isClassDeclaration(statement) ||
      ts.isEnumDeclaration(statement) ||
      ts.isModuleDeclaration(statement)) &&
    statement.name &&
    ts.isIdentifier(statement.name) &&
    statement.name.text === input.binding
  ) {
    errors.push("runtime_owner_conflicting_value_declaration");
  }
}

process.stdout.write(
  JSON.stringify({ matches, ownerAstSha256: ownerAstSha256(), errors }),
);
"""

_TS_LITERAL_OBJECT_ARRAY_CACHE: dict[str, list[dict[str, str]]] = {}


def _typescript_literal_object_array(
    *,
    source_path: str,
    source: str,
    binding: str,
    owner_ast_sha256: str,
) -> list[dict[str, str]]:
    """Parse one content-bound TypeScript object-array owner through its AST."""
    cache_key = hashlib.sha256(
        json.dumps(
            {
                "source_path": source_path,
                "source": source,
                "binding": binding,
                "owner_ast_sha256": owner_ast_sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    cached = _TS_LITERAL_OBJECT_ARRAY_CACHE.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached)
    completed = subprocess.run(  # noqa: S603 - fixed parser argument vector
        [  # noqa: S607 - repository toolchain resolves the bootstrapped Node binary
            "node",
            "--input-type=module",
            "-e",
            _TS_LITERAL_OBJECT_ARRAY_SCRIPT,
        ],
        cwd=REPO_ROOT / "apps/runtime-dashboard",
        input=json.dumps(
            {
                "sourcePath": source_path,
                "source": source,
                "binding": binding,
            }
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "TypeScript literal-array parser failed: " + completed.stderr.strip()
        )
    parsed = json.loads(completed.stdout)
    matches = parsed.get("matches") if isinstance(parsed, dict) else None
    owner_ast = (
        parsed.get("ownerAstSha256") if isinstance(parsed, dict) else None
    )
    errors = parsed.get("errors") if isinstance(parsed, dict) else None
    if (
        not isinstance(matches, list)
        or len(matches) != 1
        or not isinstance(matches[0], list)
        or owner_ast != owner_ast_sha256
        or not isinstance(errors, list)
        or errors
        or any(not isinstance(row, dict) for row in matches[0])
        or any(
            not isinstance(key, str) or not isinstance(value, str)
            for row in matches[0]
            for key, value in row.items()
        )
    ):
        raise ValueError("typescript_literal_object_array_invalid")
    rows = matches[0]
    _TS_LITERAL_OBJECT_ARRAY_CACHE[cache_key] = copy.deepcopy(rows)
    return copy.deepcopy(rows)

_TYPESCRIPT_REFERENCE_ROLES = frozenset(
    {
        "exported_declaration",
        "named_declaration",
        "variable_declaration",
        "type_property",
        "generated_schema_property",
        "object_property",
        "call_expression",
        "string_literal",
        "import_binding",
        "jsx_opening",
        "jsx_attribute",
    }
)

_TYPESCRIPT_REFERENCE_IDENTITY_PAYLOAD_KEYS = frozenset(
    {
        "version",
        "source_path",
        "role",
        "discriminator",
        "declaration_chain",
        "structural_path",
        "normalized_tokens_sha256",
    }
)

_TS_REFERENCE_CONSTRUCT_SCRIPT = r"""
import { createHash } from "node:crypto";
import path from "node:path";
import ts from "typescript";

let raw = "";
for await (const chunk of process.stdin) raw += chunk;
const input = JSON.parse(raw);
const { sources } = input;
const closedUniverse = input.closedUniverse ?? false;
const requests = input.requests ?? [{
  sourcePath: input.sourcePath,
  role: input.role,
  discriminator: input.discriminator,
}];
const dashboardRoot = process.cwd();
const repoRoot = path.resolve(dashboardRoot, "../..");
let requestedSourcePath;
let sourcePath;
let role;
let discriminator;
let sourceFile;
const config = ts.readConfigFile(
  path.join(dashboardRoot, "tsconfig.app.json"),
  ts.sys.readFile,
);
if (config.error) {
  throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, "\n"));
}
const parsedConfig = ts.parseJsonConfigFileContent(config.config, ts.sys, dashboardRoot);
if (parsedConfig.errors.length > 0) {
  throw new Error(ts.flattenDiagnosticMessageText(parsedConfig.errors[0].messageText, "\n"));
}
const compilerOptions = {
  ...parsedConfig.options,
  jsx: ts.JsxEmit.Preserve,
  module: ts.ModuleKind.ESNext,
  noLib: true,
  target: ts.ScriptTarget.Latest,
};
const virtualSources = new Map(
  Object.entries(sources).map(([relativePath, source]) => [path.resolve(repoRoot, relativePath), source]),
);
const host = ts.createCompilerHost(compilerOptions, true);
const defaultFileExists = host.fileExists.bind(host);
const defaultReadFile = host.readFile.bind(host);
const defaultGetSourceFile = host.getSourceFile.bind(host);
host.getCurrentDirectory = () => repoRoot;
function virtualSource(fileName) {
  return virtualSources.get(path.resolve(repoRoot, fileName));
}
host.fileExists = (fileName) =>
  virtualSource(fileName) !== undefined || (!closedUniverse && defaultFileExists(fileName));
host.readFile = (fileName) =>
  virtualSource(fileName) ?? (closedUniverse ? undefined : defaultReadFile(fileName));
host.getSourceFile = (fileName, languageVersion, onError, shouldCreateNewSourceFile) => {
  const source = virtualSource(fileName);
  if (source !== undefined) {
    const kind = fileName.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
    return ts.createSourceFile(fileName, source, languageVersion, true, kind);
  }
  if (closedUniverse) return undefined;
  return defaultGetSourceFile(fileName, languageVersion, onError, shouldCreateNewSourceFile);
};
host.resolveModuleNames = (moduleNames, containingFile) => moduleNames.map((specifier) => {
  const resolved = ts.resolveModuleName(
    specifier,
    path.resolve(repoRoot, containingFile),
    compilerOptions,
    host,
  ).resolvedModule;
  if (resolved) return resolved;
  if (!specifier.startsWith(".")) return undefined;
  const base = path.resolve(path.dirname(path.resolve(repoRoot, containingFile)), specifier);
  for (const extension of [".ts", ".tsx", ".mts", ".cts"]) {
    const candidate = base + extension;
    if (virtualSource(candidate) !== undefined) {
      return { resolvedFileName: candidate, extension: ts.Extension.Ts, isExternalLibraryImport: false };
    }
  }
  return undefined;
});
let programCreateCount = 0;
const program = ts.createProgram({
  rootNames: [...virtualSources.keys()],
  options: compilerOptions,
  host,
});
programCreateCount += 1;
const checker = program.getTypeChecker();
function isExported(node) {
  return Boolean(node.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword));
}

function resolvedModulePath(specifier) {
  const resolved = ts.resolveModuleName(
    specifier,
    path.resolve(repoRoot, sourcePath),
    compilerOptions,
    host,
  ).resolvedModule?.resolvedFileName;
  return resolved
    ? path.relative(repoRoot, path.resolve(resolved)).split(path.sep).join("/")
    : "unresolved";
}

function importedBinding(name) {
  let result = null;
  function scan(node) {
    if (result) return;
    if (ts.isImportDeclaration(node) && node.importClause && ts.isStringLiteral(node.moduleSpecifier)) {
      const clause = node.importClause;
      if (clause.name?.text === name) {
        result = { module: node.moduleSpecifier.text, imported: "default" };
        return;
      }
      const bindings = clause.namedBindings;
      if (bindings && ts.isNamedImports(bindings)) {
        for (const element of bindings.elements) {
          if (element.name.text === name) {
            result = { module: node.moduleSpecifier.text, imported: (element.propertyName ?? element.name).text };
            return;
          }
        }
      } else if (bindings && ts.isNamespaceImport(bindings) && bindings.name.text === name) {
        result = { module: node.moduleSpecifier.text, imported: "*" };
      }
    }
    ts.forEachChild(node, scan);
  }
  scan(sourceFile);
  return result;
}

function declarationName(node) {
  return node.name && ts.isIdentifier(node.name) ? node.name.text : null;
}

function nearest(node, predicate) {
  let current = node.parent;
  while (current) {
    if (predicate(current)) return current;
    current = current.parent;
  }
  return null;
}

function declarationChain(nameNode, prefix) {
  const symbol = checker.getSymbolAtLocation(nameNode);
  const resolved = symbol && (symbol.flags & ts.SymbolFlags.Alias)
    ? checker.getAliasedSymbol(symbol)
    : symbol;
  const declaration = resolved?.declarations?.[0] ?? symbol?.declarations?.[0];
  const declarationPath = declaration
    ? path.relative(
      repoRoot,
      path.resolve(repoRoot, declaration.getSourceFile().fileName),
    ).split(path.sep).join("/")
    : null;
  return [
    prefix,
    `symbol:${symbol?.getName() ?? "unresolved"}`,
    `resolved:${resolved?.getName() ?? "unresolved"}`,
    `declaration:${declarationPath ?? "unresolved"}:${declaration ? ts.SyntaxKind[declaration.kind] : "unresolved"}`,
  ];
}

function namedEnclosingChain(node) {
  const names = [];
  let current = node.parent;
  while (current && !ts.isSourceFile(current)) {
    if (
      (namedDeclarationKinds(current) || ts.isVariableDeclaration(current)) &&
      current.name &&
      ts.isIdentifier(current.name)
    ) {
      names.push(current.name.text);
    }
    current = current.parent;
  }
  return names.reverse();
}

function qualifiedPropertyName(node) {
  return [...namedEnclosingChain(node), node.name.getText(sourceFile)].join(".");
}

function propertyNameText(name) {
  if (
    ts.isIdentifier(name) ||
    ts.isStringLiteral(name) ||
    ts.isNumericLiteral(name)
  ) {
    return name.text;
  }
  return name.getText(sourceFile);
}

function generatedSchemaPropertyName(node) {
  if (!ts.isPropertySignature(node)) return null;
  const names = [];
  let current = node;
  while (current && !ts.isSourceFile(current)) {
    if (ts.isPropertySignature(current)) {
      names.push(propertyNameText(current.name));
    } else if (ts.isInterfaceDeclaration(current)) {
      names.push(current.name.text);
      break;
    }
    current = current.parent;
  }
  names.reverse();
  if (
    names.length !== 4 ||
    names[0] !== "components" ||
    names[1] !== "schemas"
  ) {
    return null;
  }
  return names.join(".");
}

function generatedSchemaOwner(node) {
  if (!ts.isTypeAliasDeclaration(node)) return null;
  const ownerAccess = node.type;
  if (!ts.isIndexedAccessTypeNode(ownerAccess)) return null;
  const schemasAccess = ownerAccess.objectType;
  if (!ts.isIndexedAccessTypeNode(schemasAccess)) return null;
  const owner = ownerAccess.indexType;
  const schemas = schemasAccess.indexType;
  if (
    !ts.isLiteralTypeNode(owner) ||
    !ts.isStringLiteral(owner.literal) ||
    !ts.isLiteralTypeNode(schemas) ||
    !ts.isStringLiteral(schemas.literal) ||
    schemas.literal.text !== "schemas"
  ) {
    return null;
  }
  return owner.literal.text;
}

function normalizedTokenSha256(node) {
  function semanticValue(current) {
    if (ts.isIdentifier(current)) return ["identifier", current.text];
    if (ts.isStringLiteral(current) || ts.isNoSubstitutionTemplateLiteral(current)) {
      return ["string", current.text];
    }
    if (ts.isNumericLiteral(current)) return ["number", Number(current.text)];
    return null;
  }
  function fingerprint(current) {
    const children = [];
    ts.forEachChild(current, (child) => {
      children.push(fingerprint(child));
    });
    return [ts.SyntaxKind[current.kind], semanticValue(current), children];
  }
  return createHash("sha256").update(JSON.stringify(fingerprint(node))).digest("hex");
}

function importBindingChain(node) {
  const importDeclaration = nearest(node, ts.isImportDeclaration);
  const module = importDeclaration && ts.isStringLiteral(importDeclaration.moduleSpecifier)
    ? importDeclaration.moduleSpecifier.text
    : "unresolved";
  if (ts.isImportSpecifier(node)) {
    const imported = (node.propertyName ?? node.name).text;
    return declarationChain(
      node.name,
      `import:${module}:${resolvedModulePath(module)}:${imported}:${node.name.text}`,
    );
  }
  return declarationChain(
    node.name,
    `import:${module}:${resolvedModulePath(module)}:default_or_namespace:${node.name.text}`,
  );
}

function jsxOpeningChain(node) {
  const tag = node.tagName.getText(sourceFile);
  const enclosing = namedEnclosingChain(node).join(".") || "module";
  if (ts.isIdentifier(node.tagName)) {
    const binding = importedBinding(tag);
    const importPart = binding
      ? `:import:${binding.module}:${resolvedModulePath(binding.module)}:${binding.imported}`
      : "";
    return declarationChain(node.tagName, `jsx_opening:${tag}:enclosing:${enclosing}${importPart}`);
  }
  return [`jsx_opening:${tag}`, `symbol:unresolved`, `resolved:unresolved`, `declaration:unresolved:unresolved`];
}

function jsxAttributeChain(node) {
  const opening = nearest(
    node,
    (candidate) => ts.isJsxOpeningElement(candidate) || ts.isJsxSelfClosingElement(candidate),
  );
  const tag = opening ? opening.tagName.getText(sourceFile) : "unresolved";
  const enclosing = namedEnclosingChain(node).join(".") || "module";
  return [`jsx_attribute:${tag}:${node.name.text}:enclosing:${enclosing}`, `symbol:${node.name.text}`, `resolved:${node.name.text}`, `declaration:${requestedSourcePath}:JsxAttribute`];
}

function namedDeclarationKinds(node) {
  return (
    ts.isFunctionDeclaration(node) ||
    ts.isClassDeclaration(node) ||
    ts.isEnumDeclaration(node) ||
    ts.isInterfaceDeclaration(node) ||
    ts.isTypeAliasDeclaration(node)
  );
}

function objectPropertyChain(node) {
  return declarationChain(node.name, `object_property:${qualifiedPropertyName(node)}`);
}

function callExpressionChain(node) {
  const callee = node.expression.getText(sourceFile);
  const enclosing = namedEnclosingChain(node).join(".") || "module";
  if (ts.isIdentifier(node.expression)) {
    return declarationChain(node.expression, `call:${callee}:enclosing:${enclosing}`);
  }
  return [`call:${callee}:enclosing:${enclosing}`, "symbol:unresolved", "resolved:unresolved", "declaration:unresolved:unresolved"];
}

function stringLiteralChain(node) {
  const enclosing = namedEnclosingChain(node).join(".") || "module";
  return [`string_literal:${node.text}:enclosing:${enclosing}`, `symbol:${node.text}`, `resolved:${node.text}`, `declaration:${requestedSourcePath}:StringLiteral`];
}

function nodeDiscriminator(node) {
  if ((namedDeclarationKinds(node) || ts.isVariableDeclaration(node)) && node.name && ts.isIdentifier(node.name)) return node.name.text;
  if (ts.isPropertySignature(node) && node.name) {
    return role === "generated_schema_property"
      ? generatedSchemaPropertyName(node) ?? "unresolved"
      : qualifiedPropertyName(node);
  }
  if (ts.isPropertyAssignment(node) && node.name) return qualifiedPropertyName(node);
  if (ts.isCallExpression(node)) return node.expression.getText(sourceFile);
  if (ts.isStringLiteral(node)) return node.text;
  if ((ts.isImportSpecifier(node) || ts.isNamespaceImport(node) || ts.isImportClause(node)) && node.name) return node.name.text;
  if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) return node.tagName.getText(sourceFile);
  if (ts.isJsxAttribute(node)) return node.name.text;
  return "unresolved";
}

function matchesDiscriminator(node) {
  return discriminator === "__creation_anchor__" || nodeDiscriminator(node) === discriminator;
}

let matches = [];
function visit(node, structuralPath = []) {
  if (
    role === "exported_declaration" &&
    isExported(node) &&
    namedDeclarationKinds(node) &&
    matchesDiscriminator(node)
  ) {
    matches.push({ node, declarationChain: declarationChain(node.name, `export:${discriminator}`), structuralPath });
  } else if (
    role === "named_declaration" &&
    namedDeclarationKinds(node) &&
    matchesDiscriminator(node)
  ) {
    matches.push({ node, declarationChain: declarationChain(node.name, `declaration:${discriminator}`), structuralPath });
  } else if (
    role === "variable_declaration" &&
    ts.isVariableDeclaration(node) &&
    ts.isIdentifier(node.name) &&
    matchesDiscriminator(node)
  ) {
    matches.push({ node, declarationChain: declarationChain(node.name, `variable:${discriminator}`), structuralPath });
  } else if (
    role === "generated_schema_property" &&
    ts.isPropertySignature(node) &&
    generatedSchemaPropertyName(node) !== null &&
    matchesDiscriminator(node)
  ) {
    matches.push({
      node,
      declarationChain: declarationChain(
        node.name,
        `generated_schema_property:${discriminator}`,
      ),
      structuralPath,
    });
  } else if (
    role === "type_property" &&
    ts.isPropertySignature(node) &&
    matchesDiscriminator(node)
  ) {
    matches.push({ node, declarationChain: declarationChain(node.name, `type_property:${discriminator}`), structuralPath });
  } else if (
    role === "object_property" &&
    ts.isPropertyAssignment(node) &&
    matchesDiscriminator(node)
  ) {
    matches.push({ node, declarationChain: objectPropertyChain(node), structuralPath });
  } else if (
    role === "call_expression" &&
    ts.isCallExpression(node) &&
    matchesDiscriminator(node)
  ) {
    matches.push({ node, declarationChain: callExpressionChain(node), structuralPath });
  } else if (
    role === "string_literal" &&
    ts.isStringLiteral(node) &&
    matchesDiscriminator(node)
  ) {
    matches.push({ node, declarationChain: stringLiteralChain(node), structuralPath });
  } else if (
    role === "import_binding" &&
    (ts.isImportSpecifier(node) || ts.isNamespaceImport(node) || ts.isImportClause(node)) &&
    node.name &&
    matchesDiscriminator(node)
  ) {
    matches.push({ node, declarationChain: importBindingChain(node), structuralPath });
  } else if (
    role === "jsx_opening" &&
    (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
    matchesDiscriminator(node)
  ) {
    matches.push({ node, declarationChain: jsxOpeningChain(node), structuralPath });
  } else if (
    role === "jsx_attribute" &&
    ts.isJsxAttribute(node) &&
    matchesDiscriminator(node)
  ) {
    matches.push({ node, declarationChain: jsxAttributeChain(node), structuralPath });
  }
  const children = [];
  ts.forEachChild(node, (child) => { children.push(child); });
  children.forEach((child, ordinal) =>
    visit(
      child,
      namedDeclarationKinds(child)
        ? []
        : [...structuralPath, `${ts.SyntaxKind[child.kind]}:${ordinal}`],
    ),
  );
}
const results = [];
for (const request of requests) {
  requestedSourcePath = request.sourcePath;
  sourcePath = path.resolve(repoRoot, requestedSourcePath);
  role = request.role;
  discriminator = request.discriminator;
  sourceFile = program.getSourceFiles().find(
    (file) => path.resolve(repoRoot, file.fileName) === sourcePath,
  );
  if (!sourceFile) {
    results.push({ sourceMissing: true, matches: [] });
    continue;
  }
  matches = [];
  visit(sourceFile);
  results.push({
    sourceMissing: false,
    matches: matches.map((match) => ({
      discriminator: nodeDiscriminator(match.node),
      generatedSchemaOwner: generatedSchemaOwner(match.node),
      generatedSchemaProperty: generatedSchemaPropertyName(match.node),
      structuralPath: match.structuralPath,
      declarationChain: match.declarationChain,
      normalizedTokensSha256: normalizedTokenSha256(match.node),
      startLine: sourceFile.getLineAndCharacterOfPosition(match.node.getStart(sourceFile)).line + 1,
      fullStartLine: sourceFile.getLineAndCharacterOfPosition(match.node.getFullStart()).line + 1,
      endLine: sourceFile.getLineAndCharacterOfPosition(match.node.getEnd()).line + 1,
    })),
  });
}
const countedResults = results.map((result) => ({ ...result, programCreateCount }));
process.stdout.write(JSON.stringify(input.requests ? { results: countedResults } : countedResults[0]));
"""

_TS_REFERENCE_CONSTRUCT_CACHE: dict[str, dict[str, Any]] = {}

_TS_GENERATED_CLIENT_ABSENCE_SCRIPT = r"""
import path from "node:path";
import ts from "typescript";

let raw = "";
for await (const chunk of process.stdin) raw += chunk;
const input = JSON.parse(raw);
const dashboardRoot = process.cwd();
const repoRoot = path.resolve(dashboardRoot, "../..");
const config = ts.readConfigFile(
  path.join(dashboardRoot, "tsconfig.app.json"),
  ts.sys.readFile,
);
if (config.error) {
  throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, "\n"));
}
const parsedConfig = ts.parseJsonConfigFileContent(config.config, ts.sys, dashboardRoot);
if (parsedConfig.errors.length > 0) {
  throw new Error(ts.flattenDiagnosticMessageText(parsedConfig.errors[0].messageText, "\n"));
}
const compilerOptions = {
  ...parsedConfig.options,
  jsx: ts.JsxEmit.Preserve,
  module: ts.ModuleKind.ESNext,
  noLib: true,
  target: ts.ScriptTarget.Latest,
};
const virtualSources = new Map(
  Object.entries(input.sources).map(([relativePath, source]) => [
    path.resolve(repoRoot, relativePath),
    source,
  ]),
);
const host = ts.createCompilerHost(compilerOptions, true);
host.getCurrentDirectory = () => repoRoot;
function virtualSource(fileName) {
  return virtualSources.get(path.resolve(repoRoot, fileName));
}
host.fileExists = (fileName) => virtualSource(fileName) !== undefined;
host.readFile = (fileName) => virtualSource(fileName);
host.getSourceFile = (fileName, languageVersion) => {
  const source = virtualSource(fileName);
  if (source === undefined) return undefined;
  const kind = fileName.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  return ts.createSourceFile(fileName, source, languageVersion, true, kind);
};
function resolveVirtualModule(specifier, containingFile) {
  const resolved = ts.resolveModuleName(
    specifier,
    path.resolve(repoRoot, containingFile),
    compilerOptions,
    host,
  ).resolvedModule;
  if (resolved && virtualSource(resolved.resolvedFileName) !== undefined) {
    return resolved;
  }
  if (!specifier.startsWith(".")) return undefined;
  const withoutJs = specifier.replace(/\.(?:c|m)?js$/, "");
  const base = path.resolve(path.dirname(path.resolve(repoRoot, containingFile)), withoutJs);
  for (const extension of [".ts", ".tsx", ".mts", ".cts"]) {
    const candidate = base + extension;
    if (virtualSource(candidate) !== undefined) {
      return {
        resolvedFileName: candidate,
        extension: ts.Extension.Ts,
        isExternalLibraryImport: false,
      };
    }
  }
  return undefined;
}
host.resolveModuleNames = (moduleNames, containingFile) =>
  moduleNames.map((specifier) => resolveVirtualModule(specifier, containingFile));
const program = ts.createProgram({
  rootNames: [...virtualSources.keys()],
  options: compilerOptions,
  host,
});
const checker = program.getTypeChecker();
const canonicalPath = path.resolve(repoRoot, input.canonicalPath);
const typesPath = path.resolve(repoRoot, input.typesPath);
const canonicalSource = program.getSourceFiles().find(
  (file) => path.resolve(repoRoot, file.fileName) === canonicalPath,
);
const typesSource = program.getSourceFiles().find(
  (file) => path.resolve(repoRoot, file.fileName) === typesPath,
);
const errors = [];

function sourceErrors(source, slot) {
  if (!source) {
    errors.push(`source_missing:${slot}`);
    return;
  }
  for (const diagnostic of program.getSyntacticDiagnostics(source)) {
    errors.push(
      `source_invalid:${slot}:` +
        ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n"),
    );
  }
}
sourceErrors(canonicalSource, "canonical");
sourceErrors(typesSource, "schema");

for (const source of program.getSourceFiles()) {
  if (virtualSource(source.fileName) === undefined) continue;
  const sourcePath = path.resolve(repoRoot, source.fileName);
  const relativeSourcePath = path.relative(repoRoot, source.fileName);
  if (sourcePath !== canonicalPath && sourcePath !== typesPath) {
    sourceErrors(source, `dependency:${relativeSourcePath}`);
  }
  for (const statement of source.statements) {
    if (
      !ts.isExportDeclaration(statement) ||
      !statement.moduleSpecifier ||
      !ts.isStringLiteral(statement.moduleSpecifier)
    ) {
      continue;
    }
    const specifier = statement.moduleSpecifier.text;
    const resolved = resolveVirtualModule(specifier, source.fileName);
    if (!resolved) {
      errors.push(
        `canonical_reexport_unresolved:` +
          `${relativeSourcePath}:${specifier}`,
      );
      continue;
    }
    const targetSource = program.getSourceFile(resolved.resolvedFileName);
    const targetModuleSymbol = targetSource
      ? checker.getSymbolAtLocation(targetSource) ?? targetSource.symbol
      : undefined;
    if (!targetSource || !targetModuleSymbol) {
      errors.push(
        `canonical_reexport_target_scope_missing:` +
          `${relativeSourcePath}:${specifier}`,
      );
    }
  }
}

let canonicalExports = [];
let canonicalScopeCount = 0;
if (canonicalSource) {
  const moduleSymbol = checker.getSymbolAtLocation(canonicalSource) ?? canonicalSource.symbol;
  if (moduleSymbol) {
    canonicalScopeCount = 1;
    canonicalExports = checker
      .getExportsOfModule(moduleSymbol)
      .map((symbol) => symbol.getName())
      .sort();
  } else {
    errors.push(`canonical_scope_missing:${input.canonicalPath}`);
  }
}

function propertyName(name) {
  if (
    ts.isIdentifier(name) ||
    ts.isStringLiteral(name) ||
    ts.isNumericLiteral(name)
  ) {
    return name.text;
  }
  if (
    ts.isComputedPropertyName(name) &&
    (ts.isStringLiteral(name.expression) ||
      ts.isNumericLiteral(name.expression))
  ) {
    return name.expression.text;
  }
  errors.push(`schema_owner_name_unsupported:${name.getText(typesSource)}`);
  return null;
}

const schemaScopes = [];
if (typesSource) {
  for (const statement of typesSource.statements) {
    if (
      !ts.isInterfaceDeclaration(statement) ||
      statement.name.text !== "components"
    ) {
      continue;
    }
    for (const member of statement.members) {
      if (!member.name) {
        errors.push(`schema_scope_member_unsupported:${ts.SyntaxKind[member.kind]}`);
        continue;
      }
      const memberName = propertyName(member.name);
      if (memberName !== "schemas") continue;
      if (
        !ts.isPropertySignature(member) ||
        !member.type ||
        !ts.isTypeLiteralNode(member.type)
      ) {
        errors.push(`schema_scope_shape_unsupported:${ts.SyntaxKind[member.kind]}`);
        continue;
      }
      schemaScopes.push(member.type);
    }
  }
}
let schemaOwners = [];
if (schemaScopes.length === 1) {
  for (const member of schemaScopes[0].members) {
    if (!ts.isPropertySignature(member)) {
      errors.push(`schema_owner_member_unsupported:${ts.SyntaxKind[member.kind]}`);
      continue;
    }
    const owner = propertyName(member.name);
    if (owner !== null) schemaOwners.push(owner);
  }
  schemaOwners.sort();
}

process.stdout.write(JSON.stringify({
  canonicalExports,
  canonicalScopeCount,
  schemaOwners,
  schemaScopeCount: schemaScopes.length,
  errors,
}));
"""

_TS_GENERATED_CLIENT_ABSENCE_CACHE: dict[str, dict[str, Any]] = {}


def _typescript_generated_client_absence_facts(
    sources: Mapping[str, str],
    *,
    canonical_path: str,
    types_path: str,
) -> dict[str, Any]:
    """Derive canonical exports and exact generated schema-owner membership."""
    cache_key = hashlib.sha256(
        json.dumps(
            {
                "canonical_path": canonical_path,
                "sources": sources,
                "types_path": types_path,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    cached = _TS_GENERATED_CLIENT_ABSENCE_CACHE.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached)
    completed = subprocess.run(  # noqa: S603 - fixed parser argument vector
        [  # noqa: S607 - repository toolchain resolves bootstrapped Node
            "node",
            "--input-type=module",
            "-e",
            _TS_GENERATED_CLIENT_ABSENCE_SCRIPT,
        ],
        cwd=REPO_ROOT / "apps/runtime-dashboard",
        input=json.dumps(
            {
                "canonicalPath": canonical_path,
                "sources": sources,
                "typesPath": types_path,
            }
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "TypeScript generated-client absence parser failed: "
            + completed.stderr.strip()
        )
    parsed = json.loads(completed.stdout)
    if (
        not isinstance(parsed, dict)
        or not isinstance(parsed.get("canonicalExports"), list)
        or not isinstance(parsed.get("canonicalScopeCount"), int)
        or not isinstance(parsed.get("schemaOwners"), list)
        or not isinstance(parsed.get("schemaScopeCount"), int)
        or not isinstance(parsed.get("errors"), list)
        or any(
            not isinstance(value, str)
            for key in ("canonicalExports", "schemaOwners", "errors")
            for value in parsed[key]
        )
    ):
        raise RuntimeError(
            "TypeScript generated-client absence parser returned an invalid payload"
        )
    _TS_GENERATED_CLIENT_ABSENCE_CACHE[cache_key] = copy.deepcopy(parsed)
    return parsed


def _typescript_module_facts(sources: Mapping[str, str]) -> list[dict[str, Any]]:
    """Parse TypeScript modules with the installed compiler, never text markers."""
    cache_key = hashlib.sha256(
        json.dumps(
            sources,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    cached = _TS_MODULE_FACTS_CACHE.get(cache_key)
    if cached is not None:
        return cached
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", _TS_MODULE_FACTS_SCRIPT],
        cwd=REPO_ROOT / "apps/runtime-dashboard",
        input=json.dumps(sources),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "TypeScript consumer census failed: " + completed.stderr.strip()
        )
    parsed = json.loads(completed.stdout)
    if not isinstance(parsed, list):
        raise RuntimeError("TypeScript consumer census returned a non-list payload")
    _TS_MODULE_FACTS_CACHE[cache_key] = parsed
    return parsed


def _typescript_reference_construct_facts_batch(
    sources: Mapping[str, str],
    requests: Sequence[Mapping[str, str]],
    *,
    closed_universe: bool = False,
) -> list[dict[str, Any]]:
    """Resolve many direct-syntax constructs through one TypeScript program."""
    for request in requests:
        role = request.get("role")
        if role not in _TYPESCRIPT_REFERENCE_ROLES:
            raise ValueError(f"typescript_reference_role_invalid:{role}")
    cache_key = hashlib.sha256(
        json.dumps(
            {
                "closed_universe": closed_universe,
                "sources": sources,
                "requests": requests,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    cached = _TS_REFERENCE_CONSTRUCT_CACHE.get(cache_key)
    if cached is not None:
        return cached["results"]
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", _TS_REFERENCE_CONSTRUCT_SCRIPT],
        cwd=REPO_ROOT / "apps/runtime-dashboard",
        input=json.dumps(
            {
                "closedUniverse": closed_universe,
                "sources": sources,
                "requests": requests,
            }
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "TypeScript reference identity parser failed: " + completed.stderr.strip()
        )
    parsed = json.loads(completed.stdout)
    results = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(results, list) or len(results) != len(requests):
        raise RuntimeError("TypeScript reference identity parser returned an invalid payload")
    if any(not isinstance(result, dict) or not isinstance(result.get("matches"), list) for result in results):
        raise RuntimeError("TypeScript reference identity parser returned an invalid payload")
    _TS_REFERENCE_CONSTRUCT_CACHE[cache_key] = {"results": results}
    return results


def _typescript_reference_construct_facts(
    sources: Mapping[str, str],
    *,
    source_path: str,
    role: str,
    discriminator: str,
) -> dict[str, Any]:
    """Resolve one canonical construct through the batch TypeScript program."""
    return _typescript_reference_construct_facts_batch(
        sources,
        [
            {
                "sourcePath": source_path,
                "role": role,
                "discriminator": discriminator,
            }
        ],
    )[0]


def _typescript_reference_identity(
    sources: Mapping[str, str],
    *,
    source_path: str,
    role: str,
    discriminator: str,
    navigation_hint: int | None = None,
) -> dict[str, str]:
    """Encode a stable TypeScript construct identity without source line navigation.

    ``navigation_hint`` is creation-only migration assistance. It selects a current
    AST candidate but is deliberately excluded from the encoded path reference.
    """
    facts = _typescript_reference_construct_facts(
        sources,
        source_path=source_path,
        role=role,
        discriminator=discriminator,
    )
    matches = facts["matches"]
    if navigation_hint is not None:
        matches = [
            match
            for match in matches
            if match.get("fullStartLine", 0) <= navigation_hint <= match.get("endLine", -1)
        ]
    if facts.get("sourceMissing") or len(matches) == 0:
        raise ValueError("typescript_reference_binding_missing_or_renamed")
    if len(matches) > 1:
        raise ValueError("typescript_reference_binding_ambiguous")
    match = matches[0]
    payload = {
        "version": 1,
        "source_path": source_path,
        "role": role,
        "discriminator": discriminator,
        "declaration_chain": match["declarationChain"],
        "structural_path": match["structuralPath"],
        "normalized_tokens_sha256": match["normalizedTokensSha256"],
    }
    encoded_payload = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded_identity = (
        source_path
        + "#ts-identity="
        + base64.urlsafe_b64encode(encoded_payload).decode("ascii").rstrip("=")
    )
    return {
        "source_path": source_path,
        "role": role,
        "discriminator": discriminator,
        "declaration_chain": json.dumps(match["declarationChain"], separators=(",", ":")),
        "structural_path": json.dumps(match["structuralPath"], separators=(",", ":")),
        "normalized_tokens_sha256": match["normalizedTokensSha256"],
        "encoded_identity": encoded_identity,
    }


def _typescript_reference_identity_payload(encoded_identity: str) -> dict[str, Any]:
    """Decode and strictly validate the shared v1 TypeScript identity envelope."""
    try:
        source_path, marker, encoded_payload = encoded_identity.partition("#ts-identity=")
        if not source_path or not marker or "#" in encoded_payload:
            raise ValueError
        payload = json.loads(
            base64.urlsafe_b64decode(
                encoded_payload + "=" * (-len(encoded_payload) % 4)
            )
        )
        if (
            not isinstance(payload, dict)
            or set(payload) != _TYPESCRIPT_REFERENCE_IDENTITY_PAYLOAD_KEYS
            or payload["version"] != 1
            or isinstance(payload["version"], bool)
            or payload["source_path"] != source_path
            or not isinstance(payload["source_path"], str)
            or not isinstance(payload["role"], str)
            or payload["role"] not in _TYPESCRIPT_REFERENCE_ROLES
            or not isinstance(payload["discriminator"], str)
            or not isinstance(payload["declaration_chain"], list)
            or not all(
                isinstance(part, str) for part in payload["declaration_chain"]
            )
            or not isinstance(payload["structural_path"], list)
            or not all(isinstance(part, str) for part in payload["structural_path"])
            or not isinstance(payload["normalized_tokens_sha256"], str)
        ):
            raise ValueError
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as error:
        raise ValueError("typescript_reference_identity_invalid") from error
    return payload


def _typescript_reference_identity_record(encoded_identity: str) -> dict[str, str]:
    """Decode one internally minted identity into the relocation-key input shape."""
    payload = _typescript_reference_identity_payload(encoded_identity)
    return {
        "source_path": str(payload["source_path"]),
        "role": str(payload["role"]),
        "discriminator": str(payload["discriminator"]),
        "declaration_chain": json.dumps(payload["declaration_chain"], separators=(",", ":")),
        "structural_path": json.dumps(payload["structural_path"], separators=(",", ":")),
        "normalized_tokens_sha256": str(payload["normalized_tokens_sha256"]),
        "encoded_identity": encoded_identity,
    }


def _typescript_reference_relocation_family(identity: Mapping[str, str]) -> str:
    """Hash the binding/content pair that may relocate without structural authority."""
    family = {
        "source_path": identity["source_path"],
        "role": identity["role"],
        "discriminator": identity["discriminator"],
        "declaration_chain": json.loads(identity["declaration_chain"]),
        "normalized_tokens_sha256": identity["normalized_tokens_sha256"],
    }
    return hashlib.sha256(
        b"c21d-relocation-family\0"
        + json.dumps(
            family,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _typescript_reference_hybrid_keys(
    identities: Sequence[Mapping[str, str]],
) -> list[str]:
    """Use relocation identity only for a unique declaration/content family."""
    families = [_typescript_reference_relocation_family(identity) for identity in identities]
    family_counts = Counter(families)
    return [
        family
        if family_counts[family] == 1
        else hashlib.sha256(identity["encoded_identity"].encode("utf-8")).hexdigest()
        for identity, family in zip(identities, families, strict=True)
    ]


def _typescript_reference_identities_from_anchors(
    anchors: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Create stable identities from explicit navigation-only migration anchors.

    The anchor is deliberately a creation aid: the returned identity never encodes
    its line and validation later resolves only the direct-syntax binding.
    """
    sources = {
        str(anchor["path"]): (REPO_ROOT / str(anchor["path"])).read_text(encoding="utf-8")
        for anchor in anchors
    }
    requests = [
        {
            "sourcePath": str(anchor["path"]),
            "role": str(anchor["role"]),
            "discriminator": str(anchor.get("discriminator", "__creation_anchor__")),
        }
        for anchor in anchors
    ]
    facts_by_anchor = _typescript_reference_construct_facts_batch(sources, requests)
    anchor_errors: list[str] = []
    for anchor, facts in zip(anchors, facts_by_anchor, strict=True):
        matches = _typescript_reference_anchor_matches(facts, anchor)
        diagnostic = (
            f"{anchor['path']}:{anchor['line']}:{anchor['role']}:"
            + str(anchor.get("descriptor_id", "unlabeled"))
        )
        if facts.get("sourceMissing") or not matches:
            anchor_errors.append("typescript_reference_binding_missing_or_renamed:" + diagnostic)
        elif len(matches) != 1:
            anchor_errors.append("typescript_reference_binding_ambiguous:" + diagnostic)
    if anchor_errors:
        raise ValueError(";".join(anchor_errors))
    identities: list[dict[str, str]] = []
    for anchor, facts in zip(anchors, facts_by_anchor, strict=True):
        matches = _typescript_reference_anchor_matches(facts, anchor)
        if facts.get("sourceMissing") or not matches:
            raise ValueError(
                "typescript_reference_binding_missing_or_renamed:"
                + f"{anchor['path']}:{anchor['line']}:{anchor['role']}:"
                + str(anchor.get("descriptor_id", "unlabeled"))
            )
        if len(matches) != 1:
            raise ValueError(
                "typescript_reference_binding_ambiguous:"
                + f"{anchor['path']}:{anchor['line']}:{anchor['role']}:"
                + str(anchor.get("descriptor_id", "unlabeled"))
            )
        match = matches[0]
        discriminator = str(match["discriminator"])
        source_path = str(anchor["path"])
        role = str(anchor["role"])
        declaration_chain = [
            str(part).replace("__creation_anchor__", discriminator)
            for part in match["declarationChain"]
        ]
        payload = {
            "version": 1,
            "source_path": source_path,
            "role": role,
            "discriminator": discriminator,
            "declaration_chain": declaration_chain,
            "structural_path": match["structuralPath"],
            "normalized_tokens_sha256": match["normalizedTokensSha256"],
        }
        encoded_payload = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        identities.append(
            {
                "source_path": source_path,
                "role": role,
                "discriminator": discriminator,
                "declaration_chain": json.dumps(declaration_chain, separators=(",", ":")),
                "structural_path": json.dumps(match["structuralPath"], separators=(",", ":")),
                "normalized_tokens_sha256": match["normalizedTokensSha256"],
                "encoded_identity": source_path
                + "#ts-identity="
                + base64.urlsafe_b64encode(encoded_payload).decode("ascii").rstrip("="),
            }
        )
    return identities


def _typescript_reference_anchor_matches(
    facts: Mapping[str, Any], anchor: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    """Select an AST construct by syntax start, then navigation-only containment."""
    matches = facts["matches"]
    exact_start_matches = [
            match for match in facts["matches"] if int(match.get("startLine", 0)) == int(anchor["line"])
        ]
    matches = exact_start_matches or [
            match
            for match in facts["matches"]
            if int(match.get("fullStartLine", 0)) <= int(anchor["line"]) <= int(match.get("endLine", -1))
        ]
    if not matches and anchor.get("discriminator"):
        matches = facts["matches"]
    return matches


def _typescript_reference_match_error(
    payload: Mapping[str, Any], facts: Mapping[str, Any]
) -> str | None:
    """Classify one parsed identity against facts from either parser path."""
    if facts.get("sourceMissing"):
        return "typescript_reference_source_missing"
    matches = facts["matches"]
    if not matches:
        return "typescript_reference_binding_missing_or_renamed"
    if payload.get("role") == "generated_schema_property" and len(matches) > 1:
        return "typescript_reference_binding_ambiguous"

    binding_matches = [
        match
        for match in matches
        if match["declarationChain"] == payload["declaration_chain"]
        and match["structuralPath"] == payload["structural_path"]
    ]
    if len(binding_matches) > 1:
        return "typescript_reference_binding_ambiguous"
    if binding_matches:
        if (
            binding_matches[0]["normalizedTokensSha256"]
            != payload["normalized_tokens_sha256"]
        ):
            return "typescript_reference_content_drift"
        return None

    declaration_matches = [
        match
        for match in matches
        if match["declarationChain"] == payload["declaration_chain"]
    ]
    relocation_matches = [
        match
        for match in declaration_matches
        if match["normalizedTokensSha256"] == payload["normalized_tokens_sha256"]
    ]
    if len(relocation_matches) > 1:
        return "typescript_reference_binding_ambiguous"
    if relocation_matches:
        return None
    if declaration_matches:
        return "typescript_reference_content_drift"
    return "typescript_reference_binding_missing_or_renamed"


def _validate_typescript_reference_identity(
    reference: Mapping[str, str],
    sources: Mapping[str, str],
) -> list[str]:
    """Fail closed when a canonical construct binding is absent, ambiguous, or stale."""
    try:
        encoded_identity = reference["encoded_identity"]
        if not isinstance(encoded_identity, str):
            raise ValueError
        payload = _typescript_reference_identity_payload(encoded_identity)
        source_path = payload["source_path"]
        role = payload["role"]
        discriminator = payload["discriminator"]
        expected_chain = payload["declaration_chain"]
        expected_structural_path = payload["structural_path"]
        expected_tokens_sha256 = payload["normalized_tokens_sha256"]
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ):
        return ["typescript_reference_identity_invalid"]
    facts = _typescript_reference_construct_facts(
        sources,
        source_path=source_path,
        role=role,
        discriminator=discriminator,
    )
    error = _typescript_reference_match_error(
        {
            "role": role,
            "declaration_chain": expected_chain,
            "structural_path": expected_structural_path,
            "normalized_tokens_sha256": expected_tokens_sha256,
        },
        facts,
    )
    return [error] if error is not None else []


_STRUCTURED_REFERENCE_FORMATS = frozenset({"json", "toml"})
_STRUCTURED_KEYED_SELECTOR_RE = re.compile(
    r"^(?P<collection>[^\[\]]+)\[(?P<key>[^=\[\]]+)=(?P<value>[^\[\]]+)\]$"
)


class _StructuredSelectorMissing(ValueError):
    """The stable selector did not resolve in the structured document."""


class _StructuredSelectorAmbiguous(ValueError):
    """A keyed selector resolved more than one structured document member."""


class _StructuredDuplicateKey(ValueError):
    """A JSON object repeated a key and therefore has no unique binding."""


def _reject_duplicate_json_keys(
    pairs: Sequence[tuple[str, object]],
) -> dict[str, object]:
    """Build a JSON object while rejecting Python's last-key-wins behavior."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _StructuredDuplicateKey(key)
        result[key] = value
    return result


def _structured_source_value(source: str, format_adapter: str) -> object:
    """Parse a governed JSON or TOML document through its declared adapter."""
    if format_adapter == "json":
        return json.loads(source, object_pairs_hook=_reject_duplicate_json_keys)
    if format_adapter == "toml":
        return tomllib.loads(source)
    raise ValueError("structured_reference_format_unsupported")


def _structured_selector_value(document: object, selector: str) -> object:
    """Resolve a JSON-Pointer-like selector with optional keyed-list segments."""
    if not isinstance(selector, str) or not selector.startswith("/") or selector == "/":
        raise ValueError("structured_reference_selector_invalid")
    current = document
    for raw_segment in selector.removeprefix("/").split("/"):
        if not raw_segment:
            raise ValueError("structured_reference_selector_invalid")
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        keyed = _STRUCTURED_KEYED_SELECTOR_RE.fullmatch(segment)
        if keyed is not None:
            if not isinstance(current, Mapping):
                raise _StructuredSelectorMissing
            collection = current.get(keyed.group("collection"))
            if not isinstance(collection, list):
                raise _StructuredSelectorMissing
            key = keyed.group("key")
            expected = keyed.group("value")
            matches = [
                item
                for item in collection
                if isinstance(item, Mapping)
                and key in item
                and isinstance(item[key], str)
                and item[key] == expected
            ]
            if not matches:
                raise _StructuredSelectorMissing
            if len(matches) > 1:
                raise _StructuredSelectorAmbiguous
            current = matches[0]
            continue
        if "[" in segment or "]" in segment:
            raise ValueError("structured_reference_selector_invalid")
        if not isinstance(current, Mapping) or segment not in current:
            raise _StructuredSelectorMissing
        current = current[segment]
    return current


def _normalized_structured_value_sha256(value: object) -> str:
    """Hash semantic structured content independently of source formatting/order."""
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _is_canonical_repo_relative_source_path(source_path: str) -> bool:
    """Reject address payloads that can resolve outside the governed checkout."""
    if not source_path or "\\" in source_path:
        return False
    candidate = PurePosixPath(source_path)
    if (
        candidate.is_absolute()
        or candidate.as_posix() != source_path
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        return False
    try:
        (REPO_ROOT / source_path).resolve().relative_to(REPO_ROOT.resolve())
    except (OSError, ValueError):
        return False
    return True


def _encoded_structured_reference_identity(
    *,
    source_path: str,
    format_adapter: str,
    selector: str,
    normalized_value_sha256: str,
) -> str:
    """Encode an already content-bound structured selector payload."""
    if not _is_canonical_repo_relative_source_path(source_path):
        raise ValueError("structured_reference_source_path_invalid")
    payload = {
        "version": 1,
        "source_path": source_path,
        "format_adapter": format_adapter,
        "selector": selector,
        "normalized_value_sha256": normalized_value_sha256,
    }
    encoded_payload = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return (
        source_path
        + "#structured-identity="
        + base64.urlsafe_b64encode(encoded_payload).decode("ascii").rstrip("=")
    )


def _structured_adapter_matches_path(source_path: str, format_adapter: str) -> bool:
    """Bind each structured adapter to the source format it actually parses."""
    return (format_adapter, Path(source_path).suffix.lower()) in {
        ("json", ".json"),
        ("toml", ".toml"),
    }


def _structured_reference_identity(
    sources: Mapping[str, str],
    *,
    source_path: str,
    format_adapter: str,
    selector: str,
) -> dict[str, str]:
    """Encode a stable structured selector plus its normalized selected value."""
    if not _is_canonical_repo_relative_source_path(source_path):
        raise ValueError("structured_reference_source_path_invalid")
    if format_adapter not in _STRUCTURED_REFERENCE_FORMATS:
        raise ValueError("structured_reference_format_unsupported")
    if not _structured_adapter_matches_path(source_path, format_adapter):
        raise ValueError("structured_reference_format_path_mismatch")
    if source_path not in sources:
        raise ValueError("structured_reference_source_missing")
    try:
        document = _structured_source_value(sources[source_path], format_adapter)
        selected = _structured_selector_value(document, selector)
        value_sha256 = _normalized_structured_value_sha256(selected)
    except _StructuredSelectorMissing as exc:
        raise ValueError("structured_reference_selector_missing_or_renamed") from exc
    except _StructuredSelectorAmbiguous as exc:
        raise ValueError("structured_reference_selector_ambiguous") from exc
    except (
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
        _StructuredDuplicateKey,
        TypeError,
    ) as exc:
        raise ValueError("structured_reference_source_invalid") from exc
    encoded_identity = _encoded_structured_reference_identity(
        source_path=source_path,
        format_adapter=format_adapter,
        selector=selector,
        normalized_value_sha256=value_sha256,
    )
    return {
        "source_path": source_path,
        "format_adapter": format_adapter,
        "selector": selector,
        "normalized_value_sha256": value_sha256,
        "encoded_identity": encoded_identity,
    }


def _validate_structured_reference_identity(
    reference: Mapping[str, str], sources: Mapping[str, str]
) -> list[str]:
    """Fail closed on malformed, missing, ambiguous, or stale structured bindings."""
    try:
        encoded_identity = reference["encoded_identity"]
        if not isinstance(encoded_identity, str):
            raise ValueError
        path_prefix, fragment, encoded_payload = encoded_identity.partition(
            "#structured-identity="
        )
        if not fragment or not path_prefix or "#" in encoded_payload:
            raise ValueError
        payload = json.loads(
            base64.urlsafe_b64decode(
                encoded_payload + "=" * (-len(encoded_payload) % 4)
            ),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
        version = payload["version"]
        source_path = payload["source_path"]
        format_adapter = payload["format_adapter"]
        selector = payload["selector"]
        expected_value_sha256 = payload["normalized_value_sha256"]
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ):
        return ["structured_reference_identity_invalid"]
    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "version",
            "source_path",
            "format_adapter",
            "selector",
            "normalized_value_sha256",
        }
        or version != 1
        or not isinstance(source_path, str)
        or not isinstance(format_adapter, str)
        or not isinstance(selector, str)
        or not isinstance(expected_value_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_value_sha256) is None
        or path_prefix != source_path
    ):
        return ["structured_reference_identity_invalid"]
    if format_adapter not in _STRUCTURED_REFERENCE_FORMATS:
        return ["structured_reference_format_unsupported"]
    if not _is_canonical_repo_relative_source_path(source_path):
        return ["structured_reference_source_path_invalid"]
    if not _structured_adapter_matches_path(source_path, format_adapter):
        return ["structured_reference_format_path_mismatch"]
    source = sources.get(source_path)
    if source is None:
        return ["structured_reference_source_missing"]
    try:
        document = _structured_source_value(source, format_adapter)
        selected = _structured_selector_value(document, selector)
        live_value_sha256 = _normalized_structured_value_sha256(selected)
    except _StructuredSelectorMissing:
        return ["structured_reference_selector_missing_or_renamed"]
    except _StructuredSelectorAmbiguous:
        return ["structured_reference_selector_ambiguous"]
    except ValueError as exc:
        if str(exc) == "structured_reference_selector_invalid":
            return ["structured_reference_selector_invalid"]
        return ["structured_reference_source_invalid"]
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, TypeError):
        return ["structured_reference_source_invalid"]
    if live_value_sha256 != expected_value_sha256:
        return ["structured_reference_content_drift"]
    return []


_C21C_STRUCTURED_HINTS = {
    "architecture/atlas_surfaces/ds4-waist-debt-register.json:16": (
        "json",
        "/entries[debt_id=ds4-waist-cgf-disposition]",
        "c70f0656487e81fc889b19d3f5198eb930eac5e9289d85d99c445cd4785868af",
    ),
    "architecture/atlas_surfaces/ds4-waist-debt-register.json:37": (
        "json",
        "/entries[debt_id=ds4-waist-decision-grade]",
        "621616705e0a72e62ca87bb18a23aba5b1e60dbff8d6ddadd365c31eb32d0fee",
    ),
    "schemas/runtime_api_v1.openapi.json:2221": (
        "json",
        "/components/schemas/AuthMeResponse",
        "7983a50e47d9c0a6e7785de9367614512ce2be27a3e183ac7d844cb4dba6bd3f",
    ),
    "architecture/generated_artifacts.toml:764": (
        "toml",
        "/family[id=runtime-dashboard-api-types]/outputs",
        "39d976d308c9d0ddd92032f6fafb308091469c06adc631e380e5f08606bc07fa",
    ),
    "apps/runtime-dashboard/package.json:166": (
        "json",
        "/devDependencies/openapi-typescript",
        "1a900c57304920020c1211fba15c4ad49d05cecc62e94b5e13ca67d9e79c7b56",
    ),
}

_C21C_FROZEN_STRUCTURED_IDENTITIES = {
    reference: _encoded_structured_reference_identity(
        source_path=reference.rsplit(":", 1)[0],
        format_adapter=format_adapter,
        selector=selector,
        normalized_value_sha256=value_sha256,
    )
    for reference, (
        format_adapter,
        selector,
        value_sha256,
    ) in _C21C_STRUCTURED_HINTS.items()
}


def _typescript_production_sources(scan_roots: Sequence[str]) -> dict[str, str]:
    """Load TypeScript production modules while excluding tests, stories, and output."""
    sources: dict[str, str] = {}
    for path in _iter_scan_files(scan_roots):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if path.suffix not in {".ts", ".tsx", ".mts", ".cts"}:
            continue
        if any(part in {"dist", "coverage", "tests", "e2e", ".storybook"} for part in path.parts):
            continue
        if re.search(r"\.(?:a11y\.)?(?:test|spec)\.[cm]?tsx?$|\.stories\.[cm]?tsx?$", path.name):
            continue
        sources[relative] = path.read_text(encoding="utf-8")
    return sources


RAW_TRANSPORT_SCAN_ROOTS = ("apps/runtime-dashboard/src",)
RAW_TRANSPORT_DRIFT_FINDING_ID = "raw-transport-denominator-drift"
RAW_TRANSPORT_DRIFT_DECISION_DATE = "2026-08-08"
RAW_TRANSPORT_OWNER_TEST_ABSENT_EXIT = 3
RAW_TRANSPORT_DRIFT_TEST_ABSENT_EXIT = 4
RAW_TRANSPORT_OWNER_TEST_METHOD = (
    "test_direct_authority_transport_requires_typed_purpose_factory"
)
RAW_TRANSPORT_DRIFT_TEST_METHOD = (
    "test_raw_transport_drift_row_binds_historical_and_live_census"
)
RAW_TRANSPORT_CLOSURE_SIGNAL = (
    "python3 -c 'import importlib; from architecture.atlas_surfaces import "
    "check_frontend_disposition_register as checker; owner_module=importlib.import_module("
    "\"architecture.atlas_surfaces.test_atlas_enforcement\"); drift_module=importlib.import_module("
    "\"architecture.atlas_surfaces.test_frontend_disposition_register\"); raise SystemExit("
    "checker._raw_transport_debt_closure_exit_code(getattr(owner_module, "
    "\"AtlasEnforcementTests\", None), "
    "\"test_direct_authority_transport_requires_typed_purpose_factory\", "
    "getattr(drift_module, \"RawTransportDriftTests\", None), "
    "\"test_raw_transport_drift_row_binds_historical_and_live_census\"))' "
    "# exits 0 only when both exact C03b tests execute and pass with the live 7/5 census; "
    "3 means owner "
    "test absent, 4 means drift test absent, and 1 means either test failed; all are exit nonzero."
)
RAW_TRANSPORT_HISTORICAL_AUDIT_REF = (
    "docs/reference/frontend/atlas-live-application-audit.md"
    "#hand-written-fetches-audited-9-of-9-production-calls"
)
RAW_TRANSPORT_C03B_FREEZE_REF = (
    "docs/plans/active/atlas-slices/DS5-enforcement-waist-journal.md"
    "#ds5-c03b-r2-freeze-and-c03b-d1-deferral-checkpoint-54fec7ae9a7282f414da8dc727fa5aa01a17b232-forward-revert-1d0ff1f539790294d508f97b3e4e4bfe3139f594"
)
RAW_TRANSPORT_C03B_REJECTED_CHECKPOINT = "54fec7ae9a7282f414da8dc727fa5aa01a17b232"
RAW_TRANSPORT_C03B_FORWARD_REVERT = "1d0ff1f539790294d508f97b3e4e4bfe3139f594"
RAW_TRANSPORT_DS19_DELETION_REF = (
    "docs/plans/active/atlas-slices/DS19-false-substrate-strangle-wave-journal.md"
    "#2026-07-17---collaboration-cluster-verification"
)
_DIRECT_TRANSPORT_CENSUS_SCRIPT = r"""
import ts from "typescript";

let raw = "";
for await (const chunk of process.stdin) raw += chunk;
const sources = JSON.parse(raw);
const facts = [];

for (const [path, source] of Object.entries(sources)) {
  const kind = path.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const file = ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true, kind);
  const line = (node) => file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1;
  const visit = (node) => {
    if (
      ts.isCallExpression(node)
      && ts.isIdentifier(node.expression)
      && node.expression.text === "fetch"
    ) {
      facts.push({path, line: line(node), kind: "fetch"});
    }
    if (
      ts.isNewExpression(node)
      && ts.isIdentifier(node.expression)
      && (node.expression.text === "EventSource" || node.expression.text === "WebSocket")
    ) {
      facts.push({path, line: line(node), kind: node.expression.text});
    }
    ts.forEachChild(node, visit);
  };
  visit(file);
}

process.stdout.write(JSON.stringify(facts));
"""


def _direct_transport_census_from_sources(
    sources: Mapping[str, str],
) -> dict[str, Any]:
    """Count direct raw transport syntax without following data or call flow."""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", _DIRECT_TRANSPORT_CENSUS_SCRIPT],
        cwd=REPO_ROOT / "apps/runtime-dashboard",
        input=json.dumps(sources),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "direct transport syntax census failed: " + completed.stderr.strip()
        )
    facts = json.loads(completed.stdout)
    if not isinstance(facts, list) or any(not isinstance(fact, dict) for fact in facts):
        raise RuntimeError("direct transport syntax census returned invalid facts")
    kinds = ("fetch", "EventSource", "WebSocket")
    kind_counts = {kind: sum(fact.get("kind") == kind for fact in facts) for kind in kinds}
    fetch_paths = {
        str(fact["path"])
        for fact in facts
        if fact.get("kind") == "fetch"
    }
    return {
        "direct_constructor_count": len(facts),
        "production_file_count": len({str(fact["path"]) for fact in facts}),
        "fetch_production_file_count": len(fetch_paths),
        "kind_counts": kind_counts,
    }


def _direct_transport_census(
    sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Recompute the bounded dashboard direct-constructor denominator."""
    if sources is None:
        sources = _typescript_production_sources(RAW_TRANSPORT_SCAN_ROOTS)
    return _direct_transport_census_from_sources(sources)


def _raw_transport_debt_closure_exit_code(
    owner_test_class: type[unittest.TestCase] | None,
    owner_test_method: str,
    drift_test_class: type[unittest.TestCase] | None,
    drift_test_method: str,
) -> int:
    """Run the two resolved C03b closure tests without evaluating register text."""
    if owner_test_class is None or not callable(
        getattr(owner_test_class, owner_test_method, None)
    ):
        return RAW_TRANSPORT_OWNER_TEST_ABSENT_EXIT
    if drift_test_class is None or not callable(
        getattr(drift_test_class, drift_test_method, None)
    ):
        return RAW_TRANSPORT_DRIFT_TEST_ABSENT_EXIT
    suite = unittest.TestSuite(
        (
            owner_test_class(owner_test_method),
            drift_test_class(drift_test_method),
        )
    )
    runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
    return 0 if runner.run(suite).wasSuccessful() else 1


def _raw_transport_drift_descriptor() -> dict[str, Any]:
    """Return the typed historical/live denominator distinction for C03b-R1."""
    return {
        "finding_id": RAW_TRANSPORT_DRIFT_FINDING_ID,
        "finding_kind": "producer_binding_debt",
        "disposition": "rebind_pending",
        "status": "open_debt",
        "owner_slice": "DS5",
        "decision_date": RAW_TRANSPORT_DRIFT_DECISION_DATE,
        "capability_states": [
            "contract_only",
            "consumer_missing",
            "semantic_test_missing",
        ],
        "evidence_refs": [
            RAW_TRANSPORT_HISTORICAL_AUDIT_REF,
            RAW_TRANSPORT_DS19_DELETION_REF,
            RAW_TRANSPORT_C03B_FREEZE_REF,
        ],
        "raw_transport_receipt": {
            "historical_ds1": {
                "raw_fetch_calls": 9,
                "production_file_count": 5,
                "audit_evidence_ref": RAW_TRANSPORT_HISTORICAL_AUDIT_REF,
            },
            "live_direct_constructor_census": {
                "fetch_calls": 5,
                "fetch_production_file_count": 3,
                "direct_constructor_count": 7,
                "direct_constructor_production_file_count": 5,
                "kind_counts": {"fetch": 5, "EventSource": 1, "WebSocket": 1},
            },
            "ds19_collaboration_deletion_evidence_ref": RAW_TRANSPORT_DS19_DELETION_REF,
        },
        "rationale": (
            "The DS1 audit recorded four collaboration fetches that DS19 later "
            "deleted; historical audit coverage is evidence, not the live C03b "
            "direct-call denominator. C03b-R2 exhausted its two-fix-round cap at "
            f"{RAW_TRANSPORT_C03B_REJECTED_CHECKPOINT} and was forward-reverted by "
            f"{RAW_TRANSPORT_C03B_FORWARD_REVERT}; the remaining corruption "
            "`raw_transport_live_direct_constructor_census_drift` is deferred."
        ),
        "closure_signal": RAW_TRANSPORT_CLOSURE_SIGNAL,
    }


def _owner_exports(path: str, source: str, module_prefix: str) -> set[str]:
    """Return owner module stems exported by a canonical TypeScript barrel."""
    return {
        posixpath.basename(fact["module"])
        for fact in _typescript_module_facts({path: source})
        if fact["kind"] == "export" and fact["module"].startswith(module_prefix)
    }


def _ui_primitive_owner_refs_from_sources(
    sources: Mapping[str, str],
) -> dict[str, list[str]]:
    """Find dormant primitive declarations or exported aliases in owner roots."""
    primitives = set(UI_PRIMITIVES_MEMBER_RULES)
    observed: dict[str, set[str]] = defaultdict(set)
    owner_roots = (
        "apps/runtime-dashboard/src/shared/ui/",
        "packages/atlas-ui/src/primitives/",
    )
    for fact in _typescript_module_facts(sources):
        if not fact["path"].startswith(owner_roots):
            continue
        if fact["kind"] == "owner_symbol":
            names = set(fact["names"])
        elif fact["kind"] == "export":
            names = set(fact.get("exported_names", []))
        else:
            continue
        reference = f"{fact['path']}:{fact['line']}"
        for primitive in names & primitives:
            observed[primitive].add(reference)
    return {
        primitive: sorted(references)
        for primitive, references in sorted(observed.items())
    }


def _atlas_ui_value_consumer_refs_from_sources(
    sources: Mapping[str, str],
) -> list[str]:
    """Return package import sites whose local value binding is actually used."""
    return sorted(
        {
            f"{fact['path']}:{fact['line']}"
            for fact in _typescript_module_facts(sources)
            if fact["module"] == "@polisyos/atlas-ui"
            and fact["kind"] in {"static", "dynamic"}
            and fact.get("value_binding_used") is True
        }
    )


def _c15_migrated_consumer_map_from_sources(
    sources: Mapping[str, str],
) -> dict[str, list[str]]:
    """Derive used production dashboard imports for each C15 compound."""
    observed: dict[str, set[str]] = {
        component: set() for component in C15_PACKAGE_MIGRATED
    }
    for fact in _typescript_module_facts(sources):
        source_path = fact["path"]
        if not source_path.startswith("apps/runtime-dashboard/src/"):
            continue
        if re.search(
            r"\.(?:a11y\.)?(?:test|spec)\.[cm]?tsx?$|\.stories\.[cm]?tsx?$",
            source_path,
        ):
            continue
        if fact["module"] != "@polisyos/atlas-ui":
            continue
        if fact["kind"] != "static":
            continue
        used_names = set(fact.get("jsx_element_names", []))
        reference = f"{source_path}:{fact['line']}"
        for component in used_names & C15_PACKAGE_MIGRATED:
            observed[component].add(reference)
    return {
        component: sorted(references)
        for component, references in sorted(observed.items())
    }


def _c15_migrated_consumer_errors(sources: Mapping[str, str]) -> list[str]:
    """Require localized, used dashboard imports for every C15 compound."""
    consumers = _c15_migrated_consumer_map_from_sources(sources)
    errors = [
        f"ui_compounds_root_production_consumer_missing:{component}"
        for component in sorted(C15_PACKAGE_MIGRATED)
        if not consumers[component]
    ]
    for reference in consumers["JsonPreview"]:
        consumer_path = reference.split(":", 1)[0]
        if consumer_path != C15_JSON_PREVIEW_ADAPTER:
            errors.append(
                "ui_compounds_root_unlocalized_json_preview_consumer:"
                f"{consumer_path}"
            )
    return errors


def _c16_pattern_consumer_map_from_sources(
    sources: Mapping[str, str],
) -> dict[str, list[str]]:
    """Derive direct JSX consumers for each package-migrated C16 pattern."""
    observed: dict[str, set[str]] = {
        component: set() for component in C16_PACKAGE_MIGRATED
    }
    for fact in _typescript_module_facts(sources):
        source_path = fact["path"]
        if not source_path.startswith("apps/runtime-dashboard/src/"):
            continue
        if fact["module"] != "@polisyos/atlas-ui" or fact["kind"] != "static":
            continue
        used_names = set(fact.get("jsx_element_names", []))
        for component in used_names & C16_PACKAGE_MIGRATED:
            observed[component].add(source_path)
    return {
        component: sorted(references)
        for component, references in sorted(observed.items())
    }


def _c16_searchable_list_consumers_from_sources(
    sources: Mapping[str, str],
) -> list[str]:
    """Return production JSX consumers of the dashboard-owned SearchableList."""
    allowed_modules = {
        "@/shared/ui",
        "@/shared/ui/patterns",
        "@/shared/ui/patterns/SearchableList",
        "@polisyos/atlas-ui",
    }
    return sorted(
        {
            fact["path"]
            for fact in _typescript_module_facts(sources)
            if fact["path"].startswith("apps/runtime-dashboard/src/")
            and fact["module"] in allowed_modules
            and fact["kind"] == "static"
            and C16_SEARCHABLE_LIST in set(fact.get("jsx_element_names", []))
        }
    )


def _c16_pattern_source_state_errors(
    *,
    sources: Mapping[str, str] | None = None,
    existing_paths: set[str] | None = None,
    atlas_exports: set[str] | None = None,
) -> list[str]:
    """Recompute the C16 mixed owner and production-consumer invariant."""
    if sources is None:
        sources = _typescript_production_sources(["apps/runtime-dashboard/src"])
    if existing_paths is None:
        candidates = C16_REQUIRED_PATHS | C16_RETIRED_PATHS | {
            "packages/atlas-ui/src/patterns/SearchableList.tsx"
        }
        existing_paths = {
            path for path in candidates if (REPO_ROOT / path).exists()
        }
    if atlas_exports is None:
        atlas_exports = _owner_exports(
            ATLAS_UI_INDEX,
            (REPO_ROOT / ATLAS_UI_INDEX).read_text(encoding="utf-8"),
            "./patterns/",
        )

    errors: list[str] = []
    for path in sorted(C16_REQUIRED_PATHS - existing_paths):
        errors.append(f"ui_patterns_required_path_missing:{path}")
    for path in sorted(C16_RETIRED_PATHS & existing_paths):
        errors.append(f"ui_patterns_retired_dashboard_path_survives:{path}")

    missing_exports = C16_PACKAGE_MIGRATED - atlas_exports
    if missing_exports:
        errors.append(
            "ui_patterns_package_exports_missing:"
            + ",".join(sorted(missing_exports))
        )

    consumer_map = _c16_pattern_consumer_map_from_sources(sources)
    for component, expected_paths in C16_EXPECTED_PRODUCTION_CONSUMERS.items():
        observed_paths = set(consumer_map[component])
        if not expected_paths <= observed_paths:
            errors.append(f"ui_patterns_production_consumer_missing:{component}")
        for path in sorted(observed_paths - expected_paths):
            errors.append(f"ui_patterns_unexpected_production_consumer:{component}:{path}")

    searchable_consumers = _c16_searchable_list_consumers_from_sources(sources)
    if searchable_consumers:
        errors.append("ui_patterns_searchable_list_consumer_missing_receipt_stale")
    package_searchable = "packages/atlas-ui/src/patterns/SearchableList.tsx"
    if package_searchable in existing_paths or C16_SEARCHABLE_LIST in atlas_exports:
        if not searchable_consumers:
            errors.append("ui_patterns_searchable_list_promoted_without_consumer")
        else:
            errors.append("ui_patterns_searchable_list_promotion_unadjudicated")
    return errors


def _c17_responsive_source_state_errors(
    *,
    sources: Mapping[str, str] | None = None,
    existing_paths: set[str] | None = None,
    dashboard_exports: set[str] | None = None,
    atlas_exports: set[str] | None = None,
) -> list[str]:
    """Recompute the retained responsive owners and live hook consumers."""
    if sources is None:
        sources = _typescript_production_sources(["apps/runtime-dashboard/src"])
    if existing_paths is None:
        existing_paths = {
            path for path in C17_CONSUMER_REFS if (REPO_ROOT / path).is_file()
        }
    responsive_barrel = "apps/runtime-dashboard/src/shared/ui/responsive/index.ts"
    if dashboard_exports is None:
        dashboard_exports = _owner_exports(
            responsive_barrel,
            (REPO_ROOT / responsive_barrel).read_text(encoding="utf-8"),
            "./",
        )
    if atlas_exports is None:
        atlas_exports = _owner_exports(
            ATLAS_UI_INDEX,
            (REPO_ROOT / ATLAS_UI_INDEX).read_text(encoding="utf-8"),
            "./",
        )

    errors = [
        f"ui_responsive_required_path_missing:{path}"
        for path in sorted(set(C17_CONSUMER_REFS) - existing_paths)
    ]
    required_dashboard_exports = C17_COMPONENTS | C17_HOOK_EXPORTS
    if dashboard_exports != required_dashboard_exports:
        errors.append(
            "ui_responsive_dashboard_exports_drift:"
            + ",".join(sorted(dashboard_exports))
        )
    package_twins = C17_COMPONENTS & atlas_exports
    if package_twins:
        errors.append(
            "ui_responsive_package_twin_created:" + ",".join(sorted(package_twins))
        )

    observed_consumers: dict[str, set[str]] = {
        hook: set() for hook in C17_HOOK_CONSUMERS
    }
    for fact in _typescript_module_facts(sources):
        if fact["kind"] != "static" or fact["module"] != "@/shared/ui/responsive":
            continue
        used_names = set(fact.get("used_names", []))
        for hook in used_names & set(C17_HOOK_CONSUMERS):
            observed_consumers[hook].add(fact["path"])
    for hook, expected_paths in C17_HOOK_CONSUMERS.items():
        if observed_consumers[hook] != expected_paths:
            errors.append(f"ui_responsive_hook_consumers_drift:{hook}")
    return errors


def _ui_primitives_successor_evidence_errors(
    successor_refs: Sequence[str],
    *,
    sources: Mapping[str, str] | None = None,
) -> list[str]:
    """Require listed live and test successors to consume an atlas-ui value."""
    reference_paths = {ref.split(":", 1)[0] for ref in successor_refs}
    if sources is None:
        sources = {
            path: (REPO_ROOT / path).read_text(encoding="utf-8")
            for path in reference_paths
            if (REPO_ROOT / path).is_file()
        }
    consumed_paths = {
        ref.split(":", 1)[0]
        for ref in _atlas_ui_value_consumer_refs_from_sources(sources)
    }
    listed_consumers = reference_paths & consumed_paths
    errors: list[str] = []
    if not any(
        not re.search(r"\.(?:a11y\.)?(?:test|spec)\.[cm]?tsx?$", path)
        for path in listed_consumers
    ):
        errors.append("ui_primitives_successor_live_consumer_missing")
    if not any(
        re.search(r"\.(?:a11y\.)?(?:test|spec)\.[cm]?tsx?$", path)
        for path in listed_consumers
    ):
        errors.append("ui_primitives_successor_test_consumer_missing")
    return errors


def _ui_primitive_consumer_map_from_sources(
    sources: Mapping[str, str],
) -> dict[str, list[str]]:
    """Derive dormant-primitive consumers from TypeScript module syntax."""
    primitives = set(UI_PRIMITIVES_MEMBER_RULES)
    observed: dict[str, set[str]] = {primitive: set() for primitive in primitives}

    def module_base(importer: str, module: str) -> str | None:
        if module.startswith("@/shared/ui"):
            suffix = module.removeprefix("@/")
            return f"apps/runtime-dashboard/src/{suffix}"
        if module == "@polisyos/atlas-ui":
            return "packages/atlas-ui/src/index"
        if module.startswith("@polisyos/atlas-ui/"):
            return "packages/atlas-ui/src/" + module.removeprefix(
                "@polisyos/atlas-ui/"
            )
        if module.startswith("."):
            return posixpath.normpath(
                posixpath.join(posixpath.dirname(importer), module)
            )
        return None

    def primitive_for_direct_module(base: str | None) -> str | None:
        if base is None:
            return None
        stem = re.sub(r"\.(?:[cm]?[jt]sx?)$", "", base)
        for primitive in primitives:
            if stem in {
                f"apps/runtime-dashboard/src/shared/ui/{primitive}",
                f"packages/atlas-ui/src/primitives/{primitive}",
            }:
                return primitive
        return None

    def is_barrel(base: str | None) -> bool:
        if base is None:
            return False
        stem = re.sub(r"\.(?:[cm]?[jt]sx?)$", "", base)
        return stem in {
            "apps/runtime-dashboard/src/shared/ui",
            "apps/runtime-dashboard/src/shared/ui/index",
            "apps/runtime-dashboard/src/shared/ui/primitives",
            "apps/runtime-dashboard/src/shared/ui/primitives/index",
            "packages/atlas-ui/src/index",
        }

    owner_barrels = {
        UI_PRIMITIVES_BARREL,
        "apps/runtime-dashboard/src/shared/ui/index.ts",
        ATLAS_UI_INDEX,
    }
    for fact in _typescript_module_facts(sources):
        if fact["path"] in owner_barrels:
            continue
        base = module_base(fact["path"], fact["module"])
        direct = primitive_for_direct_module(base)
        used_primitives = {direct} if direct is not None else set()
        if not used_primitives and is_barrel(base):
            if "*" in fact["names"]:
                used_primitives.update(primitives)
            used_primitives.update(set(fact["names"]) & primitives)
            used_primitives.update(set(fact["namespace_usages"]) & primitives)
        reference = f"{fact['path']}:{fact['line']}"
        for primitive in used_primitives:
            observed[primitive].add(reference)
    return {
        primitive: sorted(references)
        for primitive, references in sorted(observed.items())
    }


def _ui_primitive_consumers_from_sources(
    sources: Mapping[str, str],
) -> list[str]:
    """Flatten the per-member dormant-primitive consumer census."""
    by_primitive = _ui_primitive_consumer_map_from_sources(sources)
    return sorted({reference for references in by_primitive.values() for reference in references})


def _live_ui_primitives_source_state_errors() -> list[str]:
    """Recompute the C03b owner/export/consumer invariant from the live tree."""
    relevant_paths = {
        *UI_PRIMITIVES_DELETED_BLOBS,
        *UI_PRIMITIVES_RETAINED_PATHS,
        *(
            f"packages/atlas-ui/src/primitives/{primitive}.tsx"
            for primitive in UI_PRIMITIVES_MEMBER_RULES
        ),
        *(
            f"apps/runtime-dashboard/src/shared/ui/{primitive}.tsx"
            for primitive in UI_PRIMITIVES_DASHBOARD_REBOUND
        ),
    }
    existing_paths = {path for path in relevant_paths if (REPO_ROOT / path).exists()}
    dashboard_exports = _owner_exports(
        UI_PRIMITIVES_BARREL,
        (REPO_ROOT / UI_PRIMITIVES_BARREL).read_text(encoding="utf-8"),
        "../",
    )
    atlas_exports = _owner_exports(
        ATLAS_UI_INDEX,
        (REPO_ROOT / ATLAS_UI_INDEX).read_text(encoding="utf-8"),
        "./primitives/",
    )
    sources = _typescript_production_sources(
        ["apps/runtime-dashboard/src", "packages"]
    )
    consumers = _ui_primitive_consumers_from_sources(sources)
    owner_refs = _ui_primitive_owner_refs_from_sources(sources)
    return _ui_primitives_source_state_errors(
        existing_paths=existing_paths,
        dashboard_exports=dashboard_exports,
        atlas_exports=atlas_exports,
        production_consumers=consumers,
        owner_refs=owner_refs,
    )

CLUSTER_PROOFS = {
    "collaboration": {
        "unit_ids": COLLABORATION_IDS,
        "paths": ["apps/runtime-dashboard/src/features/collaboration"],
        "targets": [
            "@/features/collaboration",
            "features/collaboration",
            "/api/v1/collaboration",
            "collab.activity",
            "collab.comments",
            "collab.cursors",
            "collab.presence",
            "CollaborationRealtimeSubscriptionRequest",
        ],
    },
    "onboarding": {
        "unit_ids": {"feature-onboarding-orphan"},
        "paths": ["apps/runtime-dashboard/src/features/onboarding"],
        "targets": [
            "@/features/onboarding",
            "features/onboarding",
            "GuidedTour",
            "OnboardingProvider",
            "polisyos.runtime.onboarding",
        ],
    },
    "layout-placeholder": {
        "unit_ids": {"feature-layout-empty"},
        "paths": ["apps/runtime-dashboard/src/features/layout"],
        "targets": ["features/layout"],
    },
    "workers": {
        "unit_ids": {
            "worker-data-transform",
            "worker-dag-layout",
            "worker-json-parse",
        },
        "paths": [
            "apps/runtime-dashboard/src/workers/dataTransform.worker.ts",
            "apps/runtime-dashboard/src/workers/dagLayout.worker.ts",
            "apps/runtime-dashboard/src/workers/jsonParse.worker.ts",
        ],
        "targets": [
            "dataTransform.worker",
            "dagLayout.worker",
            "jsonParse.worker",
        ],
    },
    "clerk-index": {
        "unit_ids": {"route-home-clerk-duplicate"},
        "paths": ["apps/runtime-dashboard/src/features/clerk/route.tsx"],
        "targets": ["clerkChatRoute", 'routeId: "clerk.chat"'],
    },
    "whatif-local": {
        "unit_ids": {
            "cache-whatif-scenarios",
            "feature-whatif::legacy-local-whatif-subgraph",
        },
        "paths": [
            "apps/runtime-dashboard/src/features/whatif/components/WhatIfPanel.tsx",
            "apps/runtime-dashboard/src/features/whatif/components/ParameterSlider.tsx",
            "apps/runtime-dashboard/src/features/whatif/components/ImpactPreview.tsx",
            "apps/runtime-dashboard/src/features/whatif/components/ScenarioSnapshot.tsx",
            "apps/runtime-dashboard/src/features/whatif/components/index.ts",
            "apps/runtime-dashboard/src/features/whatif/state/useWhatIfStore.ts",
            "apps/runtime-dashboard/src/features/whatif/types.ts",
        ],
        "targets": [
            "WhatIfPanel",
            "ParameterSlider",
            "ImpactPreview",
            "ScenarioSnapshot",
            "useWhatIfStore",
            "polisyos.runtime.whatif",
        ],
    },
    "review-attention": {
        "unit_ids": {"cache-review-attention"},
        "paths": [
            "apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts"
        ],
        "targets": [
            "apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts"
        ],
    },
}

BASE_EXPECTED_FINDING_IDS = {
    "baseline-lint-quantity-debt",
    "baseline-test-i18n-count-debt",
    "baseline-test-a11y-rendered-contrast-incomplete-debt",
    "baseline-test-a11y-coverage-debt",
    "baseline-test-temporal-cursor-debt",
    "dependency-axe-core",
    "dependency-intl-messageformat",
    "dependency-workbox-core",
    "dependency-workbox-precaching",
    "dependency-workbox-routing",
    "dependency-workbox-window",
    "fixture-policy-design-case-audience",
}
DS6_REGISTER_TRANSITION_FINDING_IDS = {
    "baseline-test-i18n-count-debt",
    "baseline-test-a11y-rendered-contrast-incomplete-debt",
}

DS10_QUERY_KEYS_IDENTITY = (
    "apps/runtime-dashboard/src/api/queryKeys.ts#ts-identity=eyJkZWNsYXJhdGlvbl9j"
    "aGFpbiI6WyJ2YXJpYWJsZTpxdWVyeUtleXMiLCJzeW1ib2w6cXVlcnlLZXlzIiwicmVzb2x2ZWQ6"
    "cXVlcnlLZXlzIiwiZGVjbGFyYXRpb246YXBwcy9ydW50aW1lLWRhc2hib2FyZC9zcmMvYXBpL3F1"
    "ZXJ5S2V5cy50czpWYXJpYWJsZURlY2xhcmF0aW9uIl0sImRpc2NyaW1pbmF0b3IiOiJxdWVyeUtl"
    "eXMiLCJub3JtYWxpemVkX3Rva2Vuc19zaGEyNTYiOiJkNDViZDRjZWE0MDIzM2VjMzcyMTA5YWM1"
    "ZTk2M2NkNmM0NWIyZDI2MzU4ODhlYTFkNmQxNDY2OTE1MjY2OTAxIiwicm9sZSI6InZhcmlhYmxl"
    "X2RlY2xhcmF0aW9uIiwic291cmNlX3BhdGgiOiJhcHBzL3J1bnRpbWUtZGFzaGJvYXJkL3NyYy9h"
    "cGkvcXVlcnlLZXlzLnRzIiwic3RydWN0dXJhbF9wYXRoIjpbIkZpcnN0U3RhdGVtZW50OjQiLCJW"
    "YXJpYWJsZURlY2xhcmF0aW9uTGlzdDoxIiwiVmFyaWFibGVEZWNsYXJhdGlvbjowIl0sInZlcnNp"
    "b24iOjF9"
)


PRODUCER_BINDING_DEBT_DESCRIPTORS = {
    "authority-issuer-generated-semantic-id-coverage": {
        "finding_kind": "producer_binding_debt",
        "disposition": "rebind_pending",
        "status": "open_debt",
        "owner_slice": "DS5",
        "capability_states": [
            "artifact_missing",
            "verification_missing",
            "semantic_test_missing",
        ],
        "evidence_refs": [
            "architecture/atlas_surfaces/status_retirement_scan.mjs",
            "architecture/atlas_surfaces/check_atlas_enforcement.py",
            "docs/plans/active/atlas-slices/DS5-enforcement-waist-journal.md#review-fix-round-2",
            "packages/runtime-api-client/types.ts",
        ],
        "rationale": (
            "C01c review proved the scanner protects projection-state IDs but "
            "does not yet derive runtime-authority and fixture IDs from every "
            "closed generated union consumed by the issuer family."
        ),
        "closure_signal": (
            "python3 -m unittest architecture.atlas_surfaces."
            "test_atlas_enforcement.AtlasEnforcementTests."
            "test_authority_issuer_exported_vocabulary_covers_all_consumed_owner_unions "
            "exits 0 after runtime_authority and fixture_only export corruptions "
            "fail while the unrelated-constant witness remains green"
        ),
        "decision_date": "2026-08-02",
    },
    "authority-issuer-parity-operand-binding": {
        "finding_kind": "producer_binding_debt",
        "disposition": "rebind_pending",
        "status": "open_debt",
        "owner_slice": "DS5",
        "capability_states": [
            "artifact_missing",
            "verification_missing",
            "semantic_test_missing",
        ],
        "evidence_refs": [
            "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
            "architecture/atlas_surfaces/status_retirement_scan.mjs",
            "architecture/atlas_surfaces/check_atlas_enforcement.py",
            "docs/plans/active/atlas-slices/DS5-enforcement-waist-journal.md#review-fix-round-2",
        ],
        "rationale": (
            "C01c review proved the equality predicate and never branches are "
            "bound, but a generated Operator/Run operand can still be replaced "
            "by a self-comparison without invalidating the fact packet."
        ),
        "closure_signal": (
            "python3 -m unittest architecture.atlas_surfaces."
            "test_atlas_enforcement.AtlasEnforcementTests."
            "test_authority_issuer_parity_operands_are_exact_generated_pairs "
            "exits 0 after state and authority self-comparison corruptions fail"
        ),
        "decision_date": "2026-08-02",
    },
    "semantic-copy-issuer-panel-consumer-deferral": {
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
            "apps/runtime-dashboard/src/shared/ui/AuthoritySemanticCopy.ts",
            "architecture/atlas_surfaces/authority-semantic-copy-registry.json",
            "docs/plans/active/atlas-slices/DS5-enforcement-waist.md#ds5-c05b-r3",
            "docs/plans/active/atlas-slices/DS5-enforcement-waist-journal.md#ds5-c05b-r3",
        ],
        "rationale": (
            "C05b-R3 landed the private semantic-copy issuer and generated "
            "AvailableGovernedProjectionPacket.may_not_use_for guard. The live "
            "RunExplainabilityPanel/direct-Badge census transition remains panel-only "
            "debt, and DS6 accepted human semantic-review receipts remain 0."
        ),
        "closure_signal": (
            "python3 -m unittest architecture.atlas_surfaces."
            "test_frontend_disposition_register.AuthorityPresentationCensusTests."
            "test_semantic_copy_panel_consumer_rebinds_direct_badge_census_transition "
            "exits 0 after the live RunExplainabilityPanel consumer rebinds the "
            "direct-Badge census transition"
        ),
    },
    "c07b-dashboard-generated-client-single-owner-debt": {
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
            (
                "packages/runtime-api-client/types.ts#ts-identity=eyJkZWNsY"
                "XJhdGlvbl9jaGFpbiI6WyJ0eXBlX3Byb3BlcnR5OmNvbXBvbmVudHMucGV"
                "ybWlzc2lvbnMiLCJzeW1ib2w6cGVybWlzc2lvbnMiLCJyZXNvbHZlZDpwZ"
                "XJtaXNzaW9ucyIsImRlY2xhcmF0aW9uOnBhY2thZ2VzL3J1bnRpbWUtYXB"
                "pLWNsaWVudC90eXBlcy50czpQcm9wZXJ0eVNpZ25hdHVyZSJdLCJkaXNjc"
                "mltaW5hdG9yIjoiY29tcG9uZW50cy5wZXJtaXNzaW9ucyIsIm5vcm1hbGl"
                "6ZWRfdG9rZW5zX3NoYTI1NiI6IjJiNGFhNzA4MzcyY2RkNmNjYWYzYTVhY"
                "mI2ZjgwOTBiNTYxNTRjM2U0MmVkMmRjNGFkMWRhYjIwZTNlZGFkMzUiLCJ"
                "yb2xlIjoidHlwZV9wcm9wZXJ0eSIsInNvdXJjZV9wYXRoIjoicGFja2FnZ"
                "XMvcnVudGltZS1hcGktY2xpZW50L3R5cGVzLnRzIiwic3RydWN0dXJhbF9"
                "wYXRoIjpbIlByb3BlcnR5U2lnbmF0dXJlOjIiLCJUeXBlTGl0ZXJhbDoxI"
                "iwiUHJvcGVydHlTaWduYXR1cmU6NDAiLCJUeXBlTGl0ZXJhbDoxIiwiUHJ"
                "vcGVydHlTaWduYXR1cmU6NSJdLCJ2ZXJzaW9uIjoxfQ"
            ),
            (
                "apps/runtime-dashboard/src/api/types.ts#ts-identity=eyJkZWNsYXJhdGlvbl9j"
                "aGFpbiI6WyJ0eXBlX3Byb3BlcnR5OmNvbXBvbmVudHMucGVybWlzc2lvbnMiLCJzeW1ib2w6"
                "cGVybWlzc2lvbnMiLCJyZXNvbHZlZDpwZXJtaXNzaW9ucyIsImRlY2xhcmF0aW9uOmFwcHMv"
                "cnVudGltZS1kYXNoYm9hcmQvc3JjL2FwaS90eXBlcy50czpQcm9wZXJ0eVNpZ25hdHVyZSJd"
                "LCJkaXNjcmltaW5hdG9yIjoiY29tcG9uZW50cy5wZXJtaXNzaW9ucyIsIm5vcm1hbGl6ZWRf"
                "dG9rZW5zX3NoYTI1NiI6IjJiNGFhNzA4MzcyY2RkNmNjYWYzYTVhYmI2ZjgwOTBiNTYxNTRj"
                "M2U0MmVkMmRjNGFkMWRhYjIwZTNlZGFkMzUiLCJyb2xlIjoidHlwZV9wcm9wZXJ0eSIsInNv"
                "dXJjZV9wYXRoIjoiYXBwcy9ydW50aW1lLWRhc2hib2FyZC9zcmMvYXBpL3R5cGVzLnRzIiwi"
                "c3RydWN0dXJhbF9wYXRoIjpbIlByb3BlcnR5U2lnbmF0dXJlOjIiLCJUeXBlTGl0ZXJhbDox"
                "IiwiUHJvcGVydHlTaWduYXR1cmU6NDAiLCJUeXBlTGl0ZXJhbDoxIiwiUHJvcGVydHlTaWdu"
                "YXR1cmU6NSJdLCJ2ZXJzaW9uIjoxfQ"
            ),
            _C21C_FROZEN_STRUCTURED_IDENTITIES[
                "architecture/generated_artifacts.toml:764"
            ],
            "docs/reference/frontend/workspace-contract.md:37",
            _C21C_FROZEN_STRUCTURED_IDENTITIES[
                "apps/runtime-dashboard/package.json:166"
            ],
            "docs/plans/active/atlas-slices/DS5-enforcement-waist.md#ds5-c07b",
        ],
        "rationale": (
            "Canonical package client exists, but the dashboard keeps a divergent local "
            "generated artifact; this row records the single-owner strangle without a "
            "comparator or dashboard change."
        ),
        "closure_signal": (
            "python3 -m unittest architecture.atlas_surfaces.test_frontend_disposition_register."
            "ProducerBindingDebtTests.test_c07b_dashboard_generated_client_has_one_"
            "canonical_owner exits 0 after manifest/reference/package cleanup, deletion of "
            "apps/runtime-dashboard/src/api/types.ts, and all compiler-resolved dashboard "
            "imports directly use @polisyos/runtime-api-client."
        ),
    },
    "c08b-auth-session-revision-producer-debt": {
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
            _C21C_FROZEN_STRUCTURED_IDENTITIES[
                "schemas/runtime_api_v1.openapi.json:2221"
            ],
            (
                "packages/runtime-api-client/types.ts#ts-identity=eyJkZWNsY"
                "XJhdGlvbl9jaGFpbiI6WyJ0eXBlX3Byb3BlcnR5OmNvbXBvbmVudHMuQXV"
                "0aE1lUmVzcG9uc2UiLCJzeW1ib2w6QXV0aE1lUmVzcG9uc2UiLCJyZXNvb"
                "HZlZDpBdXRoTWVSZXNwb25zZSIsImRlY2xhcmF0aW9uOnBhY2thZ2VzL3J"
                "1bnRpbWUtYXBpLWNsaWVudC90eXBlcy50czpQcm9wZXJ0eVNpZ25hdHVyZ"
                "SJdLCJkaXNjcmltaW5hdG9yIjoiY29tcG9uZW50cy5BdXRoTWVSZXNwb25"
                "zZSIsIm5vcm1hbGl6ZWRfdG9rZW5zX3NoYTI1NiI6ImE5MWQ2NGU4OTdlY"
                "WYyMTQ0ZDI1MmZhMDA1NDI4YTFjOTU1ZTcxNjg5YzFhYjllMTMzMzY1YzY"
                "wZGE1MmUwMmUiLCJyb2xlIjoidHlwZV9wcm9wZXJ0eSIsInNvdXJjZV9wY"
                "XRoIjoicGFja2FnZXMvcnVudGltZS1hcGktY2xpZW50L3R5cGVzLnRzIiw"
                "ic3RydWN0dXJhbF9wYXRoIjpbIlByb3BlcnR5U2lnbmF0dXJlOjIiLCJUe"
                "XBlTGl0ZXJhbDoxIiwiUHJvcGVydHlTaWduYXR1cmU6NDAiXSwidmVyc2l"
                "vbiI6MX0"
            ),
            (
                "apps/runtime-dashboard/src/api/hooks/useAuthMe.ts#ts-ident"
                "ity=eyJkZWNsYXJhdGlvbl9jaGFpbiI6WyJkZWNsYXJhdGlvbjpmZXRjaE"
                "F1dGhNZSIsInN5bWJvbDpmZXRjaEF1dGhNZSIsInJlc29sdmVkOmZldGNo"
                "QXV0aE1lIiwiZGVjbGFyYXRpb246YXBwcy9ydW50aW1lLWRhc2hib2FyZC"
                "9zcmMvYXBpL2hvb2tzL3VzZUF1dGhNZS50czpGdW5jdGlvbkRlY2xhcmF0"
                "aW9uIl0sImRpc2NyaW1pbmF0b3IiOiJmZXRjaEF1dGhNZSIsIm5vcm1hbG"
                "l6ZWRfdG9rZW5zX3NoYTI1NiI6IjZkMjU2OWQyZTNjMjA2NjAxODY4YzU5"
                "ZWE3MGE1ZjAxMTMwNGNmMWJlNmEyNjdiYjU1MGJhNzk2ZDg5NTExYWQiLC"
                "Jyb2xlIjoibmFtZWRfZGVjbGFyYXRpb24iLCJzb3VyY2VfcGF0aCI6ImFw"
                "cHMvcnVudGltZS1kYXNoYm9hcmQvc3JjL2FwaS9ob29rcy91c2VBdXRoTW"
                "UudHMiLCJzdHJ1Y3R1cmFsX3BhdGgiOltdLCJ2ZXJzaW9uIjoxfQ"
            ),
            DS10_QUERY_KEYS_IDENTITY,
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
    },
    "c06-cgf-public-vocabulary-producer-debt": {
        "finding_kind": "producer_binding_debt",
        "disposition": "rebind_pending",
        "status": "open_debt",
        "owner_slice": "DS5",
        "capability_states": [
            "producer_missing",
            "artifact_missing",
            "bridge_missing",
            "consumer_missing",
            "verification_missing",
            "surface_missing",
            "semantic_test_missing",
        ],
        "evidence_refs": [
            _C21C_FROZEN_STRUCTURED_IDENTITIES[
                "architecture/atlas_surfaces/ds4-waist-debt-register.json:16"
            ],
            "tools/quality/validation/check_layer3_gy_generation_cycle_disposition_ledger.py:34",
            "src/polisyos/runtime/http/services/governed_projections.py:200",
            "docs/plans/active/atlas-slices/DS5-enforcement-waist.md#ds5-c06",
        ],
        "rationale": (
            "C06 cannot project CGF disposition: a private validator set exists and "
            "runtime owners remain opaque JsonObjectTuple values, but no public typed "
            "owner exists. C06 may not publish or invent that contract; the DS4 "
            "bridge/surface row remains open as a distinct plane."
        ),
        "closure_signal": (
            "python3 -m unittest architecture.atlas_surfaces.test_atlas_enforcement."
            "AtlasEnforcementTests.test_generated_cgf_disposition_union_tracks_"
            "generation_cycle_owner_contract exits 0 after the canonical generation-cycle "
            "owner publishes a public typed owner contract through the runtime schema"
        ),
    },
    "c06-decision-grade-generated-contract-debt": {
        "finding_kind": "producer_binding_debt",
        "disposition": "rebind_pending",
        "status": "open_debt",
        "owner_slice": "DS5",
        "capability_states": [
            "producer_missing",
            "artifact_missing",
            "bridge_missing",
            "consumer_missing",
            "verification_missing",
            "surface_missing",
            "semantic_test_missing",
        ],
        "evidence_refs": [
            _C21C_FROZEN_STRUCTURED_IDENTITIES[
                "architecture/atlas_surfaces/ds4-waist-debt-register.json:37"
            ],
            "src/polisyos/pdc/_impl/layer2_readiness.py:39",
            "docs/plans/active/atlas-slices/DS5-enforcement-waist.md#ds5-c06",
        ],
        "rationale": (
            "DecisionGrade has a PDC owner but no OpenAPI or generated-client export; "
            "the DS4 waist row assigns its singular swap point to C14. C06 records "
            "the missing generated producer contract and does not pre-empt C14."
        ),
        "closure_signal": (
            "python3 -m unittest architecture.atlas_surfaces.test_atlas_enforcement."
            "AtlasEnforcementTests.test_generated_decision_grade_union_tracks_pdc_owner "
            "exits 0 after C14 publishes the generated DecisionGrade contract from "
            "the PDC owner"
        ),
    },
    "producer-binding-readiness-scientific-depth": {
        "finding_kind": "producer_binding_debt",
        "disposition": "rebind_pending",
        "status": "open_debt",
        "owner_slice": "DS16",
        "capability_states": [
            "producer_missing",
            "artifact_missing",
            "bridge_missing",
            "semantic_test_missing",
        ],
        "evidence_refs": [
            "docs/plans/active/atlas-slices/DS4-status-grammar-rebinding.md#ds4-c23",
            "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:956",
            "apps/runtime-dashboard/src/features/runs/components/PublicSectorReadinessPanel.test.tsx",
            "apps/runtime-dashboard/src/features/runs/components/ScientificDepthPanel.test.tsx",
        ],
        "rationale": "dashboard-local synthesis removed because no typed producer field/refusal exists",
        "closure_signal": "each named value resolves to a generated field or registered typed refusal and C23 containment negatives remain green",
    },
    "run-lifecycle-terminal-fact": {
        "finding_kind": "producer_binding_debt",
        "disposition": "rebind_pending",
        "status": "open_debt",
        "owner_slice": "DS7",
        "capability_states": [
            "consumer_missing",
            "surface_missing",
            "semantic_test_missing",
        ],
        "evidence_refs": [
            (
                "packages/runtime-api-client/canonicalRuntimeApiClient.ts#t"
                "s-identity=eyJkZWNsYXJhdGlvbl9jaGFpbiI6WyJleHBvcnQ6UnVuU3V"
                "tbWFyeSIsInN5bWJvbDpSdW5TdW1tYXJ5IiwicmVzb2x2ZWQ6UnVuU3Vtb"
                "WFyeSIsImRlY2xhcmF0aW9uOnBhY2thZ2VzL3J1bnRpbWUtYXBpLWNsaWV"
                "udC9jYW5vbmljYWxSdW50aW1lQXBpQ2xpZW50LnRzOlR5cGVBbGlhc0RlY"
                "2xhcmF0aW9uIl0sImRpc2NyaW1pbmF0b3IiOiJSdW5TdW1tYXJ5Iiwibm9"
                "ybWFsaXplZF90b2tlbnNfc2hhMjU2IjoiZjZjZWUwZjdmMGY0ZDBkODI1N"
                "jMyMDc3YWU1MDFhYTM1OWI4NjIxZWE0ZjExN2ZjMWRlOTcwNDMyYTQ5OTF"
                "kOSIsInJvbGUiOiJleHBvcnRlZF9kZWNsYXJhdGlvbiIsInNvdXJjZV9wY"
                "XRoIjoicGFja2FnZXMvcnVudGltZS1hcGktY2xpZW50L2Nhbm9uaWNhbFJ"
                "1bnRpbWVBcGlDbGllbnQudHMiLCJzdHJ1Y3R1cmFsX3BhdGgiOltdLCJ2Z"
                "XJzaW9uIjoxfQ"
            ),
            (
                "packages/runtime-api-client/types.ts#ts-identity=eyJkZWNsYXJhdGlvbl9jaGF"
                "pbiI6WyJ0eXBlX3Byb3BlcnR5OmNvbXBvbmVudHMuUnVuU3VtbWFyeSIsInN5bWJvbDpSdW5"
                "TdW1tYXJ5IiwicmVzb2x2ZWQ6UnVuU3VtbWFyeSIsImRlY2xhcmF0aW9uOnBhY2thZ2VzL3J"
                "1bnRpbWUtYXBpLWNsaWVudC90eXBlcy50czpQcm9wZXJ0eVNpZ25hdHVyZSJdLCJkaXNjcml"
                "taW5hdG9yIjoiY29tcG9uZW50cy5SdW5TdW1tYXJ5Iiwibm9ybWFsaXplZF90b2tlbnNfc2h"
                "hMjU2IjoiZmJhNGMxYzM5M2NjZThiNjgzNWViZjUzOWEzMTE2MzNlMzI5M2RjZThhNjc4YWM"
                "0NzRjNDVlMzEzNGVhMzM1MSIsInJvbGUiOiJ0eXBlX3Byb3BlcnR5Iiwic291cmNlX3BhdGg"
                "iOiJwYWNrYWdlcy9ydW50aW1lLWFwaS1jbGllbnQvdHlwZXMudHMiLCJzdHJ1Y3R1cmFsX3B"
                "hdGgiOlsiUHJvcGVydHlTaWduYXR1cmU6MiIsIlR5cGVMaXRlcmFsOjEiLCJQcm9wZXJ0eVN"
                "pZ25hdHVyZToyOTQiXSwidmVyc2lvbiI6MX0"
            ),
            (
                "packages/runtime-api-client/types.ts#ts-identity=eyJkZWNsYXJhdGlvbl9jaGFpbiI"
                "6WyJnZW5lcmF0ZWRfc2NoZW1hX3Byb3BlcnR5OmNvbXBvbmVudHMuc2NoZW1hcy5SdW5TdW1tYXJ"
                "5LmZpbmlzaGVkX2F0Iiwic3ltYm9sOmZpbmlzaGVkX2F0IiwicmVzb2x2ZWQ6ZmluaXNoZWRfYXQ"
                "iLCJkZWNsYXJhdGlvbjpwYWNrYWdlcy9ydW50aW1lLWFwaS1jbGllbnQvdHlwZXMudHM6UHJvcGV"
                "ydHlTaWduYXR1cmUiXSwiZGlzY3JpbWluYXRvciI6ImNvbXBvbmVudHMuc2NoZW1hcy5SdW5TdW1"
                "tYXJ5LmZpbmlzaGVkX2F0Iiwibm9ybWFsaXplZF90b2tlbnNfc2hhMjU2IjoiNDE5NjZmNGRlNjA"
                "4MWI2ZDY4YWZmZmNiMmJlZGU1NDY4Zjk2OWM3ODk3MjdlZWQ2ODdlNzgwY2U3MTYwNjhiMiIsInJ"
                "vbGUiOiJnZW5lcmF0ZWRfc2NoZW1hX3Byb3BlcnR5Iiwic291cmNlX3BhdGgiOiJwYWNrYWdlcy9"
                "ydW50aW1lLWFwaS1jbGllbnQvdHlwZXMudHMiLCJzdHJ1Y3R1cmFsX3BhdGgiOlsiUHJvcGVydHl"
                "TaWduYXR1cmU6MiIsIlR5cGVMaXRlcmFsOjEiLCJQcm9wZXJ0eVNpZ25hdHVyZTozMzEiLCJUeXB"
                "lTGl0ZXJhbDoxIiwiUHJvcGVydHlTaWduYXR1cmU6OCJdLCJ2ZXJzaW9uIjoxfQ"
            ),
            (
                "packages/runtime-api-client/types.ts#ts-identity=eyJkZWNsYXJhdGlvbl9jaGFpbiI"
                "6WyJnZW5lcmF0ZWRfc2NoZW1hX3Byb3BlcnR5OmNvbXBvbmVudHMuc2NoZW1hcy5SdW5TdW1tYXJ"
                "5LnN0YXR1cyIsInN5bWJvbDpzdGF0dXMiLCJyZXNvbHZlZDpzdGF0dXMiLCJkZWNsYXJhdGlvbjp"
                "wYWNrYWdlcy9ydW50aW1lLWFwaS1jbGllbnQvdHlwZXMudHM6UHJvcGVydHlTaWduYXR1cmUiXSw"
                "iZGlzY3JpbWluYXRvciI6ImNvbXBvbmVudHMuc2NoZW1hcy5SdW5TdW1tYXJ5LnN0YXR1cyIsIm5"
                "vcm1hbGl6ZWRfdG9rZW5zX3NoYTI1NiI6IjE3ZTY3MzU0YzRlYjY5ZTkzMDUwYzRlYjczMmNlZTR"
                "kNTQxZTk5ZTY5MmI1MTU0YTk0MGE1MjY0ZWI4OWU4OWYiLCJyb2xlIjoiZ2VuZXJhdGVkX3NjaGV"
                "tYV9wcm9wZXJ0eSIsInNvdXJjZV9wYXRoIjoicGFja2FnZXMvcnVudGltZS1hcGktY2xpZW50L3R"
                "5cGVzLnRzIiwic3RydWN0dXJhbF9wYXRoIjpbIlByb3BlcnR5U2lnbmF0dXJlOjIiLCJUeXBlTGl"
                "0ZXJhbDoxIiwiUHJvcGVydHlTaWduYXR1cmU6MzMxIiwiVHlwZUxpdGVyYWw6MSIsIlByb3BlcnR"
                "5U2lnbmF0dXJlOjE2Il0sInZlcnNpb24iOjF9"
            ),
            "src/polisyos/runtime/http/services/adapters/core_run.py",
            "docs/superpowers/journals/2026-08-16-gy-gap4-run-terminality.md",
            "docs/superpowers/specs/2026-08-20-ds7-cycle-board-design.md",
        ],
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
    },
    RAW_TRANSPORT_DRIFT_FINDING_ID: _raw_transport_drift_descriptor(),
}

INTEGRATE_DEBT_DESCRIPTORS = {
    "g4-complete-audience-projection-contract": {
        "finding_id": "g4-complete-audience-projection-contract",
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
            "architecture/policy_design_case/"
            "layer3_g4_weakest_boundary_composition.json",
            "architecture/policy_design_case/"
            "layer3_g4_public_export_projection_refs.json",
            "architecture/policy_design_case/layer3_g4_readiness_manifest.json",
            "architecture/generated_artifacts.toml",
        ],
        "integrate_contract": {
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
                "owner projection supplies an owner as_of or epoch bound to the "
                "current run attempt; filesystem mtime is observation time only"
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
        },
        "rationale": (
            "The G4 owner publishes only reduced reference projections; DS5 may "
            "not invent or route the complete eight-field audience projection."
        ),
        "closure_signal": (
            "uv run python tools/quality/validation/"
            "check_policy_design_case_layer3_g4_readiness.py --repo-root . "
            "--output-format json exits 0 after owner corruptions prove the "
            "canonical projection ID and exact fields, "
            "public_export_bundle_route_registered=true, an implemented "
            "non-reference-only hook, atomic EXPERT mode.analyst denial, "
            "content hashes, owner time, and runtime novelty behavior"
        ),
        "decision_date": "2026-08-02",
    }
}

DS5_C01A_DECISION_DATE = "2026-08-02"
AUTHORITY_PRESENTATION_PLAN_REF = (
    "docs/plans/active/atlas-slices/"
    "DS5-enforcement-waist.md#ds5-c01a--authority-sink-census-and-branddebt-boundary"
)


def _authority_closure(signal: str) -> str:
    return (
        "python3 architecture/atlas_surfaces/"
        "check_frontend_disposition_register.py --check --corruption-probes "
        "exits 0 after "
        + signal
    )


AUTHORITY_PROP_CLASSIFICATIONS: dict[str, dict[str, Any]] = {
    "prop-review-presence-status": {
        "classification": "benign:interaction_state",
        "component": "ReviewPresenceSummary",
        "component_declaration_path": "apps/runtime-dashboard/src/app/realtime/ReviewCollaborationIndicators.tsx",
        "prop": "status",
        "consumer_paths": [
            "apps/runtime-dashboard/src/features/evidence/components/DataIntelligencePanel.tsx",
            "apps/runtime-dashboard/src/features/runs/routes/tabs/GovernanceTab.tsx",
        ],
    },
    "prop-control-approval-readiness": {
        "classification": "debt",
        "component": "ControlApprovalPanel",
        "component_declaration_path": "apps/runtime-dashboard/src/features/clerk/components/ControlFailurePanel.tsx",
        "prop": "readiness",
        "consumer_paths": [
            "apps/runtime-dashboard/src/features/clerk/components/ControlFailurePanel.tsx"
        ],
        "owner_slice": "DS14",
        "capability_states": [
            "producer_missing",
            "bridge_missing",
            "consumer_missing",
            "semantic_test_missing",
        ],
        "closure_signal": _authority_closure(
            "a generated approval-readiness issuer owns clothing and mixed deny/unknown cases remain non-positive"
        ),
    },
    "prop-form-section-tone": {
        "classification": "benign:layout_accent",
        "component": "AtlasFormSection",
        "component_declaration_path": "apps/runtime-dashboard/src/features/composer/routes/ComposerModeSections.tsx",
        "prop": "tone",
        "consumer_paths": [
            "apps/runtime-dashboard/src/features/composer/routes/ComposerModeSections.tsx",
            "apps/runtime-dashboard/src/features/composer/routes/ComposerModeSections.tsx",
        ],
    },
    "prop-composer-summary-tone": {
        "classification": "benign:layout_accent",
        "component": "ComposerSummaryMetric",
        "component_declaration_path": "apps/runtime-dashboard/src/features/composer/routes/LaunchRunPage.tsx",
        "prop": "tone",
        "consumer_paths": ["apps/runtime-dashboard/src/features/composer/routes/LaunchRunPage.tsx"],
    },
    "prop-decision-grade-presentation": {
        "classification": "debt",
        "component": "DecisionGradeBadge",
        "component_declaration_path": "apps/runtime-dashboard/src/features/runs/components/GovernanceComparison.tsx",
        "prop": "presentation",
        "consumer_paths": [
            "apps/runtime-dashboard/src/features/runs/components/GovernanceComparison.tsx",
            "apps/runtime-dashboard/src/features/runs/components/GovernanceComparison.tsx",
            "apps/runtime-dashboard/src/features/runs/components/GovernanceComparison.tsx",
            "apps/runtime-dashboard/src/features/runs/components/GovernanceComparison.tsx",
        ],
        "owner_slice": "DS5",
        "capability_states": ["bridge_missing", "surface_missing"],
        "closure_signal": _authority_closure(
            "C06 supplies DecisionGrade through the generated client and a private exhaustive issuer replaces this structural presentation"
        ),
    },
    "prop-authored-text-confidence": {
        "classification": "benign:captured_quantity",
        "component": "AuthoredText",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/authored-text/AuthoredText.tsx",
        "prop": "confidence",
        "consumer_paths": [
            "apps/runtime-dashboard/src/shared/ui/compounds/CandidateFrame.tsx",
            "apps/runtime-dashboard/src/features/artifacts/reading-view/MonographLayout.tsx",
        ],
    },
    "prop-data-freshness": {
        "classification": "debt",
        "component": "DataFreshnessBadge",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/compounds/DataFreshnessBadge.tsx",
        "prop": "freshness",
        "consumer_paths": [
            "apps/runtime-dashboard/src/features/runs/components/CycleBoard.tsx",
        ],
        "owner_slice": "DS18",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "ProjectionFreshness enters a private exhaustive issuer and runtime-novel states render unrecognized without cache-age inference"
        ),
    },
    "prop-decision-card-verdict": {
        "classification": "debt",
        "component": "DecisionCard",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/compounds/DecisionCard.tsx",
        "prop": "verdict",
        "consumer_paths": [
            "apps/runtime-dashboard/src/shared/ui/compounds/CandidateFrame.tsx",
            "apps/runtime-dashboard/src/features/artifacts/components/DecisionCardView.tsx",
        ],
        "owner_slice": "DS5",
        "capability_states": ["bridge_missing", "surface_missing"],
        "closure_signal": _authority_closure(
            "C06 generated DecisionGrade and a private issuer replace the raw verdict boundary with novelty tests"
        ),
    },
    "prop-decision-card-confidence": {
        "classification": "debt",
        "component": "DecisionCard",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/compounds/DecisionCard.tsx",
        "prop": "confidence",
        "consumer_paths": [
            "apps/runtime-dashboard/src/features/artifacts/components/DecisionCardView.tsx"
        ],
        "owner_slice": "DS17",
        "capability_states": ["artifact_missing", "bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a typed quantity and uncertainty artifact replaces arbitrary ReactNode confidence and rejects structural lookalikes"
        ),
    },
    "prop-explainability-verdict": {
        "classification": "debt",
        "component": "ExplainabilityCard",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/compounds/ExplainabilityCard.tsx",
        "prop": "verdict",
        "consumer_paths": [
            "apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx"
        ],
        "owner_slice": "DS5",
        "capability_states": ["bridge_missing", "surface_missing"],
        "closure_signal": _authority_closure(
            "C06 generated DecisionGrade and a private issuer replace the nested raw verdict path"
        ),
    },
    "prop-counterfactual-status": {
        "classification": "debt",
        "component": "CounterfactualBadge",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/counterfactual/CounterfactualBadge.tsx",
        "prop": "status",
        "consumer_paths": [
            "apps/runtime-dashboard/src/shared/ui/quantity/CounterfactualQuantity.tsx",
            "apps/runtime-dashboard/src/shared/ui/counterfactual/ScenarioManifestPanel.tsx",
            "apps/runtime-dashboard/src/shared/ui/counterfactual/ScenarioPicker.tsx",
        ],
        "owner_slice": "DS8",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a generated scenario-status issuer owns icon, tone, and label while novel values fail closed"
        ),
    },
    "prop-verification-status-cue": {
        "classification": "debt",
        "component": "StatusCue",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/quantity/Quantity.tsx",
        "prop": "status",
        "consumer_paths": ["apps/runtime-dashboard/src/shared/ui/quantity/Quantity.tsx"],
        "owner_slice": "DS16",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a private verification-status issuer owns cue clothing and runtime novelty is explicit"
        ),
    },
    "prop-lineage-freshness-cue": {
        "classification": "debt",
        "component": "FreshnessCue",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/quantity/Quantity.tsx",
        "prop": "freshness",
        "consumer_paths": ["apps/runtime-dashboard/src/shared/ui/quantity/Quantity.tsx"],
        "owner_slice": "DS16",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a source-owned lineage freshness issuer owns the cue and absence cannot be upgraded"
        ),
    },
    "prop-dispute-status": {
        "classification": "branded:private_trust_presentation",
        "component": "DisputeBadge",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/trust-view/DisputeBadge.tsx",
        "prop": "presentation",
        "consumer_paths": [
            "apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.tsx",
            "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
        ],
    },
    "prop-verification-status-icon-tone": {
        "classification": "branded:private_trust_presentation",
        "component": "VerificationStatus",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/trust-view/VerificationStatus.tsx",
        "prop": "presentation",
        "consumer_paths": [
            "apps/runtime-dashboard/src/shared/ui/ProvenanceStrip.tsx",
            "apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.tsx",
            "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
            "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
            "apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewBadge.tsx",
        ],
    },
    "prop-authority-badge-presentation": {
        "classification": "branded:authority_presentation",
        "component": "AuthorityBadge",
        "component_declaration_path": "packages/atlas-ui/src/primitives/AuthorityBadge.tsx",
        "prop": "presentation",
        "consumer_paths": [
            "apps/runtime-dashboard/src/shared/ui/OperatorDiagnosticPanel.tsx",
            "apps/runtime-dashboard/src/shared/ui/OperatorDiagnosticPanel.tsx",
            "apps/runtime-dashboard/src/shared/ui/OperatorDiagnosticPanel.tsx",
        ],
    },
    "prop-envelope-authority-purpose": {
        "classification": "branded:governed_authority_purpose",
        "component": "EnvelopeChip",
        "component_declaration_path": "packages/atlas-ui/src/primitives/EnvelopeChip.tsx",
        "prop": "authorityPurpose",
        "consumer_paths": [
            "apps/runtime-dashboard/src/shared/ui/compounds/DecisionCard.tsx",
        ],
    },
    "prop-segmented-control-tone": {
        "classification": "benign:responsive_layout",
        "component": "SegmentedControl",
        "component_declaration_path": "packages/atlas-ui/src/primitives/SegmentedControl.tsx",
        "prop": "tone",
        "consumer_paths": ["apps/runtime-dashboard/src/app/layout/Sidebar.tsx"],
    },
}

AUTHORITY_BADGE_DEBT_SPECS: dict[str, dict[str, Any]] = {
    "badge-review-required-aggregate": {
        "owner_slice": "DS9",
        "capability_states": ["producer_missing", "bridge_missing"],
        "closure_signal": _authority_closure(
            "signed review-required facts bind the generated run projection "
            "that already enters the private issuer"
        ),
    },
    "badge-bureaucratic-legal-review": {
        "owner_slice": "DS9",
        "capability_states": ["producer_missing", "bridge_missing"],
        "closure_signal": _authority_closure(
            "an owner-generated legal-review union replaces the local AST vocabulary "
            "already entering the exhaustive issuer"
        ),
    },
    "badge-preflight-readiness": {
        "owner_slice": "DS7",
        "capability_states": ["producer_missing", "bridge_missing", "consumer_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "typed preflight and diagnostic DTOs use mixed fail/warn veto tests and raw preview clothing is absent"
        ),
    },
    "badge-artifact-pipeline-decision-grade": {
        "owner_slice": "DS5",
        "capability_states": ["producer_missing", "consumer_missing", "verification_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "C06 exports DecisionGrade through the generated client and a private exhaustive issuer handles runtime novelty"
        ),
    },
    "badge-control-approval-quality": {
        "owner_slice": "DS9",
        "capability_states": ["producer_missing", "bridge_missing"],
        "closure_signal": _authority_closure(
            "generated approval, calibration, and gate DTOs bind the weakest-boundary "
            "issuer already covered by mixed-outcome tests"
        ),
    },
    "badge-promotion-candidate-status": {
        "owner_slice": "DS15",
        "capability_states": ["consumer_missing", "verification_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a generated promotion union enters a private issuer and novel values render unrecognized"
        ),
    },
    "badge-acquisition-boundary-status": {
        "owner_slice": "DS15",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "generated acquisition authority, qualification, quarantine, eligibility, "
            "and cost-availability unions enter a private issuer and copy cannot upgrade "
            "a negative or unknown owner state"
        ),
    },
    "badge-evidence-source-freshness": {
        "owner_slice": "DS8",
        "capability_states": ["producer_missing", "bridge_missing", "consumer_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "owner source_as_of and freshness fields enforce oldest-input veto without local SLA authority"
        ),
    },
    "badge-comparability": {
        "owner_slice": "DS16",
        "capability_states": ["consumer_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a generated comparability union uses an incomparable veto and runtime-novelty tests"
        ),
    },
    "badge-provenance-drift": {
        "owner_slice": "DS16",
        "capability_states": ["consumer_missing", "verification_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a private invalidation-posture issuer vetoes on every load-bearing provenance change"
        ),
    },
    "badge-run-deck-authority-summary": {
        "owner_slice": "DS7",
        "capability_states": ["producer_missing", "bridge_missing", "consumer_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a live typed run-deck contract rejects fixture_only and prevents local authority synthesis"
        ),
    },
    "badge-compound-decision-grade": {
        "owner_slice": "DS5",
        "capability_states": ["bridge_missing", "surface_missing"],
        "closure_signal": _authority_closure(
            "C06 generated DecisionGrade and a private exhaustive issuer make raw grade assignment fail typecheck"
        ),
    },
    "badge-governance-issue-severity": {
        "owner_slice": "DS9",
        "capability_states": ["producer_missing", "bridge_missing"],
        "closure_signal": _authority_closure(
            "a generated closed owner severity field replaces the open string already "
            "preserved as unrecognized by the issuer"
        ),
    },
    "badge-public-packet-authority-framing": {
        "owner_slice": "DS12",
        "capability_states": ["producer_missing", "artifact_missing", "bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "generated packet authority, confidence, and rights fields retain a rights-bar mixed-veto test"
        ),
    },
    "badge-governed-projection-availability": {
        "owner_slice": "DS7",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a generated availability union enters an exhaustive issuer and novel values render unrecognized"
        ),
    },
    "badge-uncertainty-dispute": {
        "owner_slice": "DS16",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "an owner uncertainty artifact keeps disputed as a mixed-case veto or warning"
        ),
    },
    "badge-operator-blocker-overridability": {
        "owner_slice": "DS14",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a generated decision or boolean issuer owns clothing and raw slot assignment fails typecheck"
        ),
    },
    "badge-candidate-declared-authority-purpose": {
        "owner_slice": "DS8",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a candidate-purpose issuer cannot grant governed authority"
        ),
    },
    "badge-projection-source-freshness": {
        "owner_slice": "DS18",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "ProjectionFreshness state enters an exhaustive issuer with explicit absence and novelty behavior"
        ),
    },
    "badge-decision-confidence": {
        "owner_slice": "DS16",
        "capability_states": ["artifact_missing", "bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a typed quantity and uncertainty artifact replaces arbitrary ReactNode confidence"
        ),
    },
    "badge-explainability-governance-counts": {
        "owner_slice": "DS9",
        "capability_states": ["producer_missing", "bridge_missing"],
        "closure_signal": _authority_closure(
            "a producer-owned governance summary binds the informational count issuer "
            "that cannot synthesize composed authority"
        ),
    },
    "badge-negative-certificate-blocker": {
        "owner_slice": "DS8",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a generated blocker issuer prevents non-blockers from occupying the slot"
        ),
    },
    "badge-public-integrity-result": {
        "owner_slice": "DS12",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a verifier-private integrity presentation remains explicitly outside closeout authority"
        ),
    },
    "badge-public-anti-authority-role": {
        "owner_slice": "DS12",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a branded refusal from packet authorityRole cannot be upgraded to authority"
        ),
    },
    "badge-threshold-unavailable": {
        "owner_slice": "DS16",
        "capability_states": ["artifact_missing", "bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a typed unavailable or refusal artifact replaces the static caller-owned threshold token"
        ),
    },
    "badge-candidate-refusal-markers": {
        "owner_slice": "DS8",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "typed candidate and refusal postures cannot be presented as governed output"
        ),
    },
}

DS9_C07_DECISION_DATE = "2026-08-24"
DS9_C07_ROOT_SCOPE = {
    "route-run-governance": "in_scope",
    "cache-local-disputes": "in_scope",
    "cache-review-attention": "in_scope_tombstone",
    "cache-operator-craft": "surface_out_of_scope",
    "feature-evidence": "surface_out_of_scope",
    "api-op-list-data-promotion-candidates": "surface_out_of_scope",
    "api-op-approve-data-promotion": "surface_out_of_scope",
    "api-op-reject-data-promotion": "surface_out_of_scope",
    "route-compose": "surface_out_of_scope",
    "feature-composer": "surface_out_of_scope",
    "api-op-launch-run": "surface_out_of_scope",
    "api-op-get-governance-debug": "surface_out_of_scope",
    "derivation-composer-readiness": "surface_out_of_scope",
}
DS9_C07_SCOPE_SEED_RULE = {
    "in_scope": "ds9_c07_human_decision_in_scope",
    "in_scope_tombstone": "ds9_c07_human_decision_in_scope_tombstone",
    "surface_out_of_scope": "ds9_c07_human_decision_surface_out_of_scope",
}
DS9_C07_OPENING_SEED_RULE = {
    **{
        unit_id: "ds1_incomplete_rebind_pending"
        for unit_id in DS9_C07_ROOT_SCOPE
        if unit_id != "cache-review-attention"
    },
    "cache-review-attention": "ds5_c17b_review_attention_deletion",
}
DS9_C07_OPENING_ROOT_RATIONALES = {
    **{
        unit_id: (
            "DS1 does not record this narrow unit as implemented; its owning "
            "slice must rebind or retire it without creating a parallel owner."
        )
        for unit_id in DS9_C07_ROOT_SCOPE
        if unit_id not in {"cache-local-disputes", "cache-review-attention"}
    },
    "cache-local-disputes": (
        "C16b-R2 replaces unscoped raw dispute bytes with the canonical "
        "tenant/user/run-bound authority-local-state envelope, a writer-owned "
        "24-hour TTL, a strict topology-only codec that omits actor and status "
        "and rehydrates reviewer/open interaction state, receipt-gated fail-closed "
        "storage, clock, codec, and getter handling, and synchronous remove "
        "ordering; DS9 server, epoch, rule-version, and dispute-authority semantics "
        "remain unclaimed."
    ),
    "cache-review-attention": (
        "DS4 commit bc1d01001 deleted the review-attention storage owner; C17b "
        "re-proves the exact source path absent and every static, barrel, namespace, "
        "relative, dynamic, and composition import form at zero without claiming "
        "DS9 semantics."
    ),
}
DS9_C07_ROOT_RATIONALES = {
    unit_id: (
        f"DS9 C07 adjudicates semantic_scope={scope} for human-decision "
        "integrity while preserving the root's formal disposition, owner, "
        "successor, and census. This is not a family-complete claim. Prior "
        f"receipt: {DS9_C07_OPENING_ROOT_RATIONALES[unit_id]}"
    )
    for unit_id, scope in DS9_C07_ROOT_SCOPE.items()
}
DS9_C07_ROOT_FORMAL = {
    **{
        unit_id: {
            "disposition": "rebind_pending",
            "strangle_status": "pending",
            "owner": "team-design",
            "owner_slice": "DS9",
            "successor_unit_id": None,
            "reference_census_id": None,
        }
        for unit_id in DS9_C07_ROOT_SCOPE
        if unit_id not in {"cache-local-disputes", "cache-review-attention"}
    },
    "cache-local-disputes": {
        "disposition": "rebind_pending",
        "strangle_status": "strangled",
        "owner": "team-design",
        "owner_slice": "DS9",
        "successor_unit_id": "dashboard-dispute-scoped-local-state",
        "reference_census_id": None,
    },
    "cache-review-attention": {
        "disposition": "deleted",
        "strangle_status": "strangled",
        "owner": "team-design",
        "owner_slice": "DS9",
        "successor_unit_id": None,
        "reference_census_id": "census-review-attention-delete",
    },
}
DS9_C07_LOCAL_DISPUTE_SUCCESSOR_REFS = [
    "apps/runtime-dashboard/src/features/runs/domain/disputes.ts",
    "apps/runtime-dashboard/src/features/runs/domain/disputes.test.ts",
    "apps/runtime-dashboard/src/features/runs/components/DisputeRegistryPanel.tsx",
    "apps/runtime-dashboard/src/features/runs/components/DisputeRegistryPanel.test.tsx",
]
DS9_C07_AUTHORITY_FINDING_IDS = frozenset(
    {
        "authority-presentation-badge-bureaucratic-legal-review",
        "authority-presentation-badge-control-approval-quality",
        "authority-presentation-badge-explainability-governance-counts",
        "authority-presentation-badge-governance-issue-severity",
        "authority-presentation-badge-review-required-aggregate",
    }
)
DS9_C07_INDUCED_SUPPLEMENTAL_RECEIPT_IDS = frozenset(
    {
        "authority-presentation-prop-control-approval-readiness",
        "authority-presentation-prop-explainability-verdict",
        "c08b-auth-session-revision-producer-debt",
    }
)
DS9_C07_REFRESH_FINDING_IDS = (
    DS9_C07_AUTHORITY_FINDING_IDS | DS9_C07_INDUCED_SUPPLEMENTAL_RECEIPT_IDS
)
DS9_C07_OPENING_FAMILY_SHA256 = {
    REGISTER_PATH: "f75d358b005886c8e4f6166b855b9de0f979c86a98c83bec8c3d46f8c19b8a63",
    REPORT_PATH: "28341305151cdfc1c8057f18277b0c8019414259a46f8431824f0070e09361db",
    STATUS_INVENTORY_PATH: ("0dbe4aade5a58a9bd3ee7f3fe5fc8d4a05a406e063da7f034dcbd5bc2c66d5b5"),
}
DS9_C07_SUPERSEDED_FAMILY_SHA256 = {
    REGISTER_PATH: "0641f14347061ef9efdf2355534910dd81046f458117bdb829e54ddb16d403be",
    REPORT_PATH: "3733dcdc0e9548a2507a75e2583a089b9153fae3480461c0a9353d46ad13e760",
    STATUS_INVENTORY_PATH: ("4a54b0b4a5558574c718aa4050daeaa2dd8010565fa9df30777250c997bed196"),
}
DS9_C07_AUTHORITY_SOURCE_PATHS = (
    Path(__file__).resolve(),
    REPO_ROOT / "apps/runtime-dashboard/src/api/queryKeys.ts",
    REPO_ROOT / "apps/runtime-dashboard/src/shared/ui/AuthorityStatusPresentation.ts",
    REPO_ROOT / "apps/runtime-dashboard/src/app/layout/Header.tsx",
    REPO_ROOT
    / "apps/runtime-dashboard/src/features/artifacts/bureaucratic/BureaucraticTemplateBadge.tsx",
    REPO_ROOT / "apps/runtime-dashboard/src/features/clerk/components/ControlFailurePanel.tsx",
    REPO_ROOT / "apps/runtime-dashboard/src/shared/ui/compounds/ExplainabilityCard.tsx",
    REPO_ROOT / "apps/runtime-dashboard/src/features/runs/components/GovernanceReport.tsx",
    REPO_ROOT / "apps/runtime-dashboard/src/features/runs/routes/tabs/OverviewTab.tsx",
    REPO_ROOT / "apps/runtime-dashboard/src/features/runs/components/HumanDecisionGate.tsx",
    REPO_ROOT
    / (
        "apps/runtime-dashboard/src/features/runs/components/"
        "HumanDecisionReviewEffectivenessPanel.tsx"
    ),
    REPO_ROOT / "apps/runtime-dashboard/src/features/runs/domain/disputes.ts",
)
DS9_C07_STORAGE_FACTORY_ID = (
    "authority-factory-6e3f26a1bcb469ffcbc97bd425b5e85de835d4a97573ed958f27bc9a8ae90d34"
)
DS9_C07_STORAGE_SITE_ID = (
    "storage-site-f51ff807af1565a3557c7e53a8d6c2e4a29f4b66a8dc86806c34ae8ea6e98f70"
)
DS9_C07_STORAGE_SOURCE_PATH = "apps/runtime-dashboard/src/features/runs/domain/disputes.ts"
DS9_C07_STORAGE_OPENING_SOURCE_SHA256 = (
    "sha256:03fe198af004454eea0e16f8b1749216e8217bc1e868a784d3d4b339ae40fe6e"
)
if len(DS9_C07_ROOT_SCOPE) + len(DS9_C07_AUTHORITY_FINDING_IDS) != 18:
    raise RuntimeError("DS9 C07 adjudication denominator drift")

BENIGN_BADGE_BASES = (
    "interaction_or_editor_state",
    "transport_or_runtime_health",
    "workflow_or_lifecycle_display_without_terminality_inference",
    "layout_or_counts",
    "opaque_metadata_or_taxonomy",
)

BENIGN_BADGE_CLASS_COUNTS: dict[str, int] = {
    "interaction_or_editor_state": 14,
    "transport_or_runtime_health": 22,
    "workflow_or_lifecycle_display_without_terminality_inference": 28,
    "layout_or_counts": 19,
    "opaque_metadata_or_taxonomy": 24,
}

if set(BENIGN_BADGE_CLASS_COUNTS) != set(BENIGN_BADGE_BASES):
    raise RuntimeError("benign Badge class vocabulary drift")
if sum(BENIGN_BADGE_CLASS_COUNTS.values()) != 107:
    raise RuntimeError("benign Badge class count drift")

DS11_TRUST_PRESENTATION_FINDING_IDS = frozenset(
    {
        "authority-presentation-prop-dispute-status",
        "authority-presentation-prop-verification-status-icon-tone",
    }
)
DS11_TRUST_PRESENTATION_DESCRIPTOR_IDS = frozenset(
    finding_id.removeprefix("authority-presentation-")
    for finding_id in DS11_TRUST_PRESENTATION_FINDING_IDS
)
DS11_C04_DECISION_DATE = "2026-08-27"
DS11_TRUST_GLYPHS_PATH = "apps/runtime-dashboard/src/shared/ui/trust-view/trust-glyphs.ts"
DS11_C04_MECHANISM_PATHS = (
    "apps/runtime-dashboard/src/shared/ui/trust-view/trust-glyphs.ts",
    "apps/runtime-dashboard/src/shared/ui/trust-view/DisputeBadge.tsx",
    "apps/runtime-dashboard/src/shared/ui/trust-view/VerificationStatus.tsx",
    "apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.tsx",
    "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
    "apps/runtime-dashboard/src/shared/ui/trust-view/index.ts",
    "apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewBadge.tsx",
    "apps/runtime-dashboard/src/shared/ui/ProvenanceStrip.tsx",
)
DS11_C04_ISSUER_CALLERS = (
    "apps/runtime-dashboard/src/shared/ui/ProvenanceStrip.tsx",
    "apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.tsx",
    "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
    "apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewBadge.tsx",
)
DS11_C04_OPENING_ROW_SHA256 = {
    "authority-presentation-prop-dispute-status": (
        "669820665d7425076730ab3e7be3a6d6c7be2bd8bf918f0f0bbb5820cc840847"
    ),
    "authority-presentation-prop-verification-status-icon-tone": (
        "24fb91517620644aeb6b4de8f66e3f6e6cfd3d2d2dfc6658d8e0d54605fc1c18"
    ),
}
DS11_RAW_TRUST_ROOT_DESCRIPTORS = (
    {
        "descriptorId": "ds11-raw-dispute-status",
        "component": "DisputeBadge",
        "componentDeclarationPath": "apps/runtime-dashboard/src/shared/ui/trust-view/DisputeBadge.tsx",
        "prop": "status",
    },
    {
        "descriptorId": "ds11-raw-verification-status-icon-tone",
        "component": "StatusIcon",
        "componentDeclarationPath": "apps/runtime-dashboard/src/shared/ui/trust-view/VerificationStatus.tsx",
        "prop": "tone",
    },
)
if set(DS11_C04_OPENING_ROW_SHA256) != DS11_TRUST_PRESENTATION_FINDING_IDS:
    raise RuntimeError("DS11 C04 opening-row denominator drift")

AUTHORITY_PRESENTATION_DEBT_SPECS = {
    "authority-presentation-" + descriptor_id: spec
    for descriptor_id, spec in AUTHORITY_PROP_CLASSIFICATIONS.items()
    if spec["classification"] == "debt"
}
AUTHORITY_PRESENTATION_DEBT_SPECS.update(
    {
        "authority-presentation-" + descriptor_id: spec
        for descriptor_id, spec in AUTHORITY_BADGE_DEBT_SPECS.items()
    }
)

AUTHORITY_PRESENTATION_COUNTS = {
    "badge_total": 172,
    "badge_branded": 6,
    "badge_debt": 59,
    "badge_benign": 107,
    "prop_total": 18,
    "prop_branded": 4,
    "prop_debt": 9,
    "prop_benign": 5,
    "prop_use_total": 34,
    "prop_use_branded": 11,
    "prop_use_debt": 15,
    "prop_use_benign": 8,
}
AUTHORITY_BADGE_PARTITION_SHA256 = (
    "sha256:a6e22fb4982717dcde705496e4e19545ef0f5d5f6afdba9f791ada09a3a70274"
)
AUTHORITY_PROP_PARTITION_SHA256 = (
    "sha256:d41e26792102015380983470c5a4d91e57cd86ecd7e95b0cc61fc7798d2bd55f"
)


def _authority_prop_descriptors() -> list[dict[str, str]]:
    """Project the finite, declaration-anchored prop census into the scanner."""
    return [
        {
            "descriptorId": descriptor_id,
            "component": str(spec["component"]),
            "componentDeclarationPath": str(spec["component_declaration_path"]),
            "prop": str(spec["prop"]),
        }
        for descriptor_id, spec in sorted(AUTHORITY_PROP_CLASSIFICATIONS.items())
    ]


def _ds11_trust_presentation_path_descriptors() -> list[dict[str, str]]:
    """Return the two repaired Trust View sink declarations for brand tracing."""
    return [
        descriptor
        for descriptor in _authority_prop_descriptors()
        if descriptor["descriptorId"]
        in {
            "prop-dispute-status",
            "prop-verification-status-icon-tone",
        }
    ]


@lru_cache(maxsize=1)
def _authority_presentation_scan() -> dict[str, Any]:
    """Return the live finite sink census; no value-flow inference is performed."""
    request = {
        "authorityPathDescriptors": _ds11_trust_presentation_path_descriptors(),
        "authorityPropDescriptors": _authority_prop_descriptors(),
        "authorityIssuerCallerPaths": DS11_C04_ISSUER_CALLERS,
    }
    return status_checker._scan_json(
        json.dumps(request, sort_keys=True, separators=(",", ":"))
    )


def _site_location(site: Mapping[str, Any]) -> tuple[str, int]:
    return (str(site.get("path", "")), int(site.get("line", 0)))


def _badge_classification_errors(
    scan: Mapping[str, Any],
    classifications: Mapping[str, str] | None = None,
) -> list[str]:
    """Validate the exact 172-site Badge partition as a finite set property."""
    errors: list[str] = []
    sites = scan.get("badgeSites", [])
    if not isinstance(sites, list):
        return ["authority_badge_census_invalid"]
    frozen_badges, _frozen_props = _frozen_authority_identity_config()
    classifications = classifications or frozen_badges
    live_locations = {
        _site_location(site)
        for site in sites
        if isinstance(site, Mapping)
    }
    live_identity_by_location = _authority_badge_live_identity_by_location(sites)
    live_identity_rows = [
        _typescript_reference_identity_record(identity)
        for identity in live_identity_by_location.values()
    ]
    live_key_by_location = dict(
        zip(
            live_identity_by_location,
            _typescript_reference_hybrid_keys(live_identity_rows),
            strict=True,
        )
    )
    locations_by_key: defaultdict[str, list[tuple[str, int]]] = defaultdict(list)
    for location, key in live_key_by_location.items():
        locations_by_key[key].append(location)
    for key, locations in sorted(locations_by_key.items()):
        if len(locations) > 1:
            errors.append(
                "typescript_reference_binding_ambiguous:"
                + key
                + ":"
                + ",".join(f"{path}:{line}" for path, line in sorted(locations))
            )
    live_identities = set(live_key_by_location.values())
    configured_identities = set(classifications)
    for path, line in sorted(live_locations):
        if live_key_by_location[(path, line)] not in configured_identities:
            errors.append(f"authority_badge_unclassified:{path}:{line}")
    for identity in sorted(configured_identities - live_identities):
        errors.append(f"authority_badge_stale_classification:{identity}")
    for identity in sorted(configured_identities & set(frozen_badges)):
        observed = classifications[identity]
        expected = frozen_badges[identity]
        if observed != expected:
            errors.append(
                "authority_badge_reclassification:"
                + f"{identity}:{expected}:{observed}"
            )

    categories = Counter(
        "debt"
        if value.startswith("debt:")
        else "branded"
        if value.startswith("branded:")
        else "benign"
        if value.startswith("benign:")
        else "invalid"
        for identity, value in classifications.items()
        if identity in live_identities
    )
    exact_classifications = Counter(
        value
        for identity, value in classifications.items()
        if identity in live_identities
    )
    expected_counts = {
        "branded": AUTHORITY_PRESENTATION_COUNTS["badge_branded"],
        "debt": AUTHORITY_PRESENTATION_COUNTS["badge_debt"],
        "benign": AUTHORITY_PRESENTATION_COUNTS["badge_benign"],
    }
    if len(live_locations) != AUTHORITY_PRESENTATION_COUNTS["badge_total"]:
        errors.append(
            "authority_badge_count_drift:"
            + f"expected={AUTHORITY_PRESENTATION_COUNTS['badge_total']}:"
            + f"actual={len(live_locations)}"
        )
    for category, expected_count in expected_counts.items():
        if categories[category] != expected_count:
            errors.append(
                f"authority_badge_{category}_count_drift:"
                + f"expected={expected_count}:actual={categories[category]}"
            )
    if categories["invalid"]:
        errors.append(
            f"authority_badge_invalid_classification:{categories['invalid']}"
        )
    for benign_class, expected_count in sorted(BENIGN_BADGE_CLASS_COUNTS.items()):
        observed_count = exact_classifications[f"benign:{benign_class}"]
        if observed_count != expected_count:
            errors.append(
                f"authority_badge_benign_class_count_drift:{benign_class}:"
                + f"expected={expected_count}:actual={observed_count}"
            )
    debt_sites_by_group = _authority_badge_sites_by_debt_group(
        {"badgeSites": sites},
        classifications=classifications,
        live_key_by_location=live_key_by_location,
    )
    for group_id in sorted(AUTHORITY_BADGE_DEBT_SPECS):
        expected_identities = {
            identity
            for identity, classification in frozen_badges.items()
            if classification == f"debt:{group_id}"
        }
        observed_identities = {
            live_key_by_location[_site_location(site)]
            for site in debt_sites_by_group[group_id]
        }
        if observed_identities != expected_identities:
            errors.append(f"authority_badge_group_drift:{group_id}")
    if live_identities <= configured_identities:
        partition_rows = sorted(
            [
                {
                    "identity": live_key_by_location[_site_location(site)],
                    "site_sha256": str(site.get("siteSha256", "")),
                    "classification": classifications[live_key_by_location[_site_location(site)]],
                }
                for site in sites
                if isinstance(site, Mapping)
            ],
            key=lambda row: (row["identity"], row["site_sha256"]),
        )
        partition_sha256 = "sha256:" + hashlib.sha256(
            json.dumps(
                partition_rows,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        if partition_sha256 != AUTHORITY_BADGE_PARTITION_SHA256:
            errors.append(
                "authority_badge_partition_hash_drift:"
                + f"expected={AUTHORITY_BADGE_PARTITION_SHA256}:"
                + f"actual={partition_sha256}"
            )
    return errors


def _authority_prop_classification_errors(scan: Mapping[str, Any]) -> list[str]:
    """Validate the exact declaration/use identity of all 18 prop groups."""
    errors: list[str] = []
    facts = scan.get("authorityPropCensus", [])
    if not isinstance(facts, list):
        return ["authority_prop_census_invalid"]
    by_id = {
        str(fact.get("descriptorId")): fact
        for fact in facts
        if isinstance(fact, Mapping)
    }
    _frozen_badges, frozen_props = _frozen_authority_identity_config()
    live_anchors: list[dict[str, Any]] = []
    live_records: list[dict[str, str]] = []
    live_identity_by_record: defaultdict[tuple[str, str], list[str]] = defaultdict(
        list
    )
    live_identity_ready = False
    for descriptor_id, spec in AUTHORITY_PROP_CLASSIFICATIONS.items():
        fact = by_id.get(descriptor_id)
        if not isinstance(fact, Mapping):
            continue
        live_anchors.extend(
            [
                {"path": fact["componentDeclarationPath"], "line": fact["componentDeclarationLine"], "role": "named_declaration", "discriminator": fact["component"], "descriptor_id": descriptor_id},
                {"path": fact["propDeclarationPath"], "line": fact["propDeclarationLine"], "role": "type_property", "descriptor_id": descriptor_id},
            ]
        )
        live_records.extend(
            [
                {"descriptor_id": descriptor_id, "classification": str(spec["classification"]), "role": "component_declaration"},
                {"descriptor_id": descriptor_id, "classification": str(spec["classification"]), "role": "prop_declaration"},
            ]
        )
        for site in fact.get("consumerSites", []):
            if not isinstance(site, Mapping):
                continue
            live_anchors.append({"path": site["path"], "line": site["line"], "role": "jsx_attribute", "discriminator": fact["prop"], "descriptor_id": descriptor_id})
            live_records.append({"descriptor_id": descriptor_id, "classification": str(spec["classification"]), "role": "consumer"})
    try:
        live_identities = _typescript_reference_identities_from_anchors(live_anchors)
    except ValueError as exc:
        errors.append(str(exc))
    else:
        live_identity_ready = True
        live_props: dict[str, list[dict[str, str]]] = {}
        live_keys = _typescript_reference_hybrid_keys(live_identities)
        for _identity, key, record in zip(
            live_identities, live_keys, live_records, strict=True
        ):
            live_identity_by_record[(record["descriptor_id"], record["role"])].append(
                key
            )
            live_props.setdefault(key, []).append(record)
        if {
            digest: sorted(records, key=lambda record: (record["descriptor_id"], record["role"]))
            for digest, records in live_props.items()
        } != {
            digest: sorted(records, key=lambda record: (record["descriptor_id"], record["role"]))
            for digest, records in frozen_props.items()
        }:
            errors.append("authority_prop_frozen_identity_drift")
    if set(by_id) != set(AUTHORITY_PROP_CLASSIFICATIONS):
        errors.append(
            "authority_prop_descriptor_drift:missing="
            + str(sorted(set(AUTHORITY_PROP_CLASSIFICATIONS) - set(by_id)))
            + ":extra="
            + str(sorted(set(by_id) - set(AUTHORITY_PROP_CLASSIFICATIONS)))
        )
    observed_counts: Counter[str] = Counter()
    observed_use_counts: Counter[str] = Counter()
    for descriptor_id, spec in sorted(AUTHORITY_PROP_CLASSIFICATIONS.items()):
        fact = by_id.get(descriptor_id)
        if fact is None:
            continue
        classification = str(spec["classification"]).split(":", 1)[0]
        observed_counts[classification] += 1
        consumer_sites = fact.get("consumerSites", [])
        observed_use_counts[classification] += (
            len(consumer_sites) if isinstance(consumer_sites, list) else 0
        )
        expected_identity = {
            "component": spec["component"],
            "componentDeclarationPath": spec["component_declaration_path"],
            "prop": spec["prop"],
            "propDeclarationPath": spec["component_declaration_path"],
        }
        for field, expected_value in expected_identity.items():
            if fact.get(field) != expected_value:
                errors.append(f"authority_prop_identity_drift:{descriptor_id}:{field}")
        expected_uses = sorted(spec["consumer_paths"])
        observed_uses = sorted(
            str(site.get("path"))
            for site in consumer_sites
            if isinstance(site, Mapping)
        )
        if observed_uses != expected_uses:
            errors.append(f"authority_prop_consumer_drift:{descriptor_id}")
        for hash_field in (
            "componentDeclarationSha256",
            "propDeclarationSha256",
        ):
            value = fact.get(hash_field)
            if not isinstance(value, str) or not re.fullmatch(
                r"sha256:[a-f0-9]{64}", value
            ):
                errors.append(f"authority_prop_fingerprint_missing:{descriptor_id}:{hash_field}")
        for site in consumer_sites if isinstance(consumer_sites, list) else []:
            value = site.get("siteSha256") if isinstance(site, Mapping) else None
            if not isinstance(value, str) or not re.fullmatch(
                r"sha256:[a-f0-9]{64}", value
            ):
                errors.append(f"authority_prop_site_fingerprint_missing:{descriptor_id}")

    expected_counts = {
        "branded": AUTHORITY_PRESENTATION_COUNTS["prop_branded"],
        "debt": AUTHORITY_PRESENTATION_COUNTS["prop_debt"],
        "benign": AUTHORITY_PRESENTATION_COUNTS["prop_benign"],
    }
    expected_use_counts = {
        "branded": AUTHORITY_PRESENTATION_COUNTS["prop_use_branded"],
        "debt": AUTHORITY_PRESENTATION_COUNTS["prop_use_debt"],
        "benign": AUTHORITY_PRESENTATION_COUNTS["prop_use_benign"],
    }
    for category, expected_count in expected_counts.items():
        if observed_counts[category] != expected_count:
            errors.append(f"authority_prop_{category}_count_drift")
        if observed_use_counts[category] != expected_use_counts[category]:
            errors.append(f"authority_prop_{category}_use_count_drift")
    if len(by_id) != AUTHORITY_PRESENTATION_COUNTS["prop_total"]:
        errors.append("authority_prop_total_count_drift")
    if sum(observed_use_counts.values()) != AUTHORITY_PRESENTATION_COUNTS["prop_use_total"]:
        errors.append("authority_prop_use_total_count_drift")
    if live_identity_ready and set(by_id) == set(AUTHORITY_PROP_CLASSIFICATIONS):
        partition_rows = []
        for descriptor_id, spec in sorted(AUTHORITY_PROP_CLASSIFICATIONS.items()):
            fact = by_id[descriptor_id]
            consumer_sites = fact.get("consumerSites", [])
            partition_rows.append(
                {
                    "descriptor_id": descriptor_id,
                    "classification": spec["classification"],
                    "component": fact.get("component"),
                    "component_declaration_identity": live_identity_by_record[(descriptor_id, "component_declaration")][0],
                    "component_declaration_sha256": fact.get(
                        "componentDeclarationSha256"
                    ),
                    "prop": fact.get("prop"),
                    "prop_declaration_identity": live_identity_by_record[(descriptor_id, "prop_declaration")][0],
                    "prop_declaration_sha256": fact.get(
                        "propDeclarationSha256"
                    ),
                    "consumer_sites": sorted(
                        [
                            {
                                "identity": live_identity_by_record[(descriptor_id, "consumer")][index],
                                "site_sha256": site.get("siteSha256"),
                            }
                            for index, site in enumerate(consumer_sites)
                            if isinstance(site, Mapping)
                        ],
                        key=lambda row: (
                            str(row["identity"]),
                            str(row["site_sha256"]),
                        ),
                    ),
                }
            )
        partition_sha256 = "sha256:" + hashlib.sha256(
            json.dumps(
                partition_rows,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        if partition_sha256 != AUTHORITY_PROP_PARTITION_SHA256:
            errors.append(
                "authority_prop_partition_hash_drift:"
                + f"expected={AUTHORITY_PROP_PARTITION_SHA256}:"
                + f"actual={partition_sha256}"
            )
    return errors


def _source_receipt(
    *, role: str, path: str, line: int, sha256: str, site: bool = False
) -> dict[str, Any]:
    receipt: dict[str, Any] = {"role": role, "path": path, "line": line}
    receipt["site_sha256" if site else "content_sha256"] = sha256
    return receipt


def _authority_evidence_identities(scan: Mapping[str, Any]) -> dict[tuple[str, int, str], str]:
    """Create all authority evidence identities through one source snapshot/program."""
    anchors: list[dict[str, Any]] = []
    for descriptor_id, spec in AUTHORITY_PROP_CLASSIFICATIONS.items():
        if (
            spec["classification"] != "debt"
            and descriptor_id not in DS11_TRUST_PRESENTATION_DESCRIPTOR_IDS
        ):
            continue
        fact = next(
            item for item in scan["authorityPropCensus"] if item["descriptorId"] == descriptor_id
        )
        anchors.append(
            {"path": fact["componentDeclarationPath"], "line": fact["componentDeclarationLine"], "role": "named_declaration", "discriminator": fact["component"]}
        )
        anchors.extend(
            {"path": site["path"], "line": site["line"], "role": "jsx_attribute", "discriminator": fact["prop"]}
            for site in fact["consumerSites"]
        )
    debt_sites_by_group = _authority_badge_sites_by_debt_group(scan)
    for group_id in AUTHORITY_BADGE_DEBT_SPECS:
        sites = debt_sites_by_group[group_id]
        if not sites:
            continue
        first = sites[0]
        anchors.append(
            {"path": first["componentDeclarationPath"], "line": first["componentDeclarationLine"], "role": "named_declaration", "discriminator": first["component"]}
        )
        anchors.extend(
            {"path": site["path"], "line": site["line"], "role": "jsx_opening", "discriminator": "Badge"}
            for site in sites
        )
    identities = _typescript_reference_identities_from_anchors(anchors)
    return {
        (str(anchor["path"]), int(anchor["line"]), str(anchor["role"])): identity["encoded_identity"]
        for anchor, identity in zip(anchors, identities, strict=True)
    }


def _authority_badge_live_identity_by_location(
    sites: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, int], str]:
    """Resolve current direct Badge syntax to its stable classification identity."""
    anchors = [
        {"path": site["path"], "line": site["line"], "role": "jsx_opening", "discriminator": "Badge"}
        for site in sites
    ]
    identities = _typescript_reference_identities_from_anchors(anchors)
    return {
        _site_location(site): identity["encoded_identity"]
        for site, identity in zip(sites, identities, strict=True)
    }


def _authority_badge_sites_by_debt_group(
    scan: Mapping[str, Any],
    *,
    classifications: Mapping[str, str] | None = None,
    live_key_by_location: Mapping[tuple[str, int], str] | None = None,
) -> dict[str, list[Mapping[str, Any]]]:
    """Group live debt sites by their line-free frozen classification identity."""
    sites = [site for site in scan.get("badgeSites", []) if isinstance(site, Mapping)]
    frozen_badges, _frozen_props = _frozen_authority_identity_config()
    classifications = classifications or frozen_badges
    if live_key_by_location is None:
        live_identities = _authority_badge_live_identity_by_location(sites)
        identity_rows = [
            _typescript_reference_identity_record(identity)
            for identity in live_identities.values()
        ]
        live_key_by_location = dict(
            zip(
                live_identities,
                _typescript_reference_hybrid_keys(identity_rows),
                strict=True,
            )
        )
    grouped = {group_id: [] for group_id in AUTHORITY_BADGE_DEBT_SPECS}
    for site in sites:
        classification = classifications.get(
            live_key_by_location[_site_location(site)], ""
        )
        if classification.startswith("debt:"):
            group_id = classification.removeprefix("debt:")
            if group_id in grouped:
                grouped[group_id].append(site)
    return grouped


# C21B_FROZEN_AUTHORITY_IDENTITIES_BEGIN
# Frozen from the root-owned no-write C21d hybrid-key receipt. Unique
# declaration/content families relocate; genuine collisions retain structural identity.
FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS: dict[str, str] = {
    '0124de230c2013b547c6c7e4c94944afc801d7f3da751ba6067806e49ae3437f': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '0132d8d97b3f44fbca967c039540f8bb1e61ad9934ad6e53dced7f37fcdf660c': (
        'benign:transport_or_runtime_health'
    ),
    '062c1fe3f9e5ecaa59f778b965257dbc63be53dd48f0750430b4cf02631e73e3': (
        'benign:layout_or_counts'
    ),
    '078599fe50e49c45b6b69803352191205b7409a7e9f382d25019887b1e56fab1': (
        'benign:transport_or_runtime_health'
    ),
    '0975deb3026c856f342cdb39c794dfa4ba8330e71504c957f9925437544cf9fa': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '0ad59fd60f80e424424dc14ad83b160cb48394ad294ad3844d8455bf3544e9de': (
        'debt:badge-provenance-drift'
    ),
    '0b4ac8ba80f99e7e9d1bff295a1829fc21accba56ddf0fee804568f642dbcebe': (
        'benign:layout_or_counts'
    ),
    '0cbe26958fdbe6d578d16890500e7a353575b48fe8c8c6bf5515b444dca99164': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '0ccc46a2e3c1cfab2522bc4f4dbc22bdfbfc9f6f22351287a7053a6c8450f2aa': (
        'benign:transport_or_runtime_health'
    ),
    '0d01fe86a863e406d0bfb676b74f4637a2102952207f1721aa1be40a332cf55e': (
        'debt:badge-control-approval-quality'
    ),
    '0d02be3c6130a3b628b630687a44aa17c3758ffda106bf5ff46a74baadcc7ec4': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '0ef26827e7122cfff8edb79967bce02979742d84ad52825be64b530b0853935e': (
        'debt:badge-run-deck-authority-summary'
    ),
    '116aa85ec7f5abe277667d64833a6bf469453309f2ce3e891188e21ce410bb3b': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '128486fc6ce4ef95c9ce2410f03c0d79b82a7aeccbfe9735a36c8b611b87b49c': (
        'debt:badge-projection-source-freshness'
    ),
    '12d25f70a1e4d12752533d44a2ff623892cf8a0324712949d2fd9a114372e264': (
        'debt:badge-public-integrity-result'
    ),
    '135b70bf4ba02dd4cbf39d810beaaeca8c7472f93bd90c790c7662801b1a76cf': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '14a3b807641e72cf79ecaaa83dd98249a6fa5ecebfbdb8434de52e93f9ee239d': (
        'benign:layout_or_counts'
    ),
    '14fbd20acffc634f412e1e4619831144afdf0698b8c60afa76a91ef16251f12f': (
        'debt:badge-explainability-governance-counts'
    ),
    '168d23a2e7bbd0b65d5239812cf87afad12e77f4c5ab14c8a58ec9d1d276b415': (
        'debt:badge-control-approval-quality'
    ),
    '16950ecbf6fed6faf6a6d058a4e03dfc850ac9326c49df23b1ac67ec33efeb0d': (
        'benign:layout_or_counts'
    ),
    '188038e809c5f6b4bcfdc8744185e9b9ea4f5841e2f2aa45c057a5e86f064946': (
        'benign:interaction_or_editor_state'
    ),
    '18c241f1f9f5ca3a237baf71f0cb7509c6f95113bc983fa3863a0d51cdf41cac': (
        'debt:badge-promotion-candidate-status'
    ),
    '19705539d0d15dbd5f66bf771c2ac39d62871075d237f115ebc145d372548e8d': (
        'benign:interaction_or_editor_state'
    ),
    '1de29932d949fb40855f0a72b9792efdc7323a920d54e721dd9138ab44fa5ae6': (
        'benign:transport_or_runtime_health'
    ),
    '1e01bb02aa403bfae75475c5ffe5346af68c654fc554bf1c544535e82bae724c': (
        'debt:badge-public-packet-authority-framing'
    ),
    '22c2a2e7b9b3c9c07fcff8e313559f5e18f31abf5fef96c074ed58da84765c75': (
        'debt:badge-run-deck-authority-summary'
    ),
    '2353ac212cdc4f28d6919059be719db9a21c2f357a9ff81637d034bde30e96d0': (
        'debt:badge-public-packet-authority-framing'
    ),
    '24e1864e260b849cc456c772ce930bd535053d95129542d9c531cd0d66bbad9a': (
        'benign:layout_or_counts'
    ),
    '258dd4eb0f8640e78aa80cbe6085a6b731e6e7ff33dd20e39776d6c097a73866': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '2700e01e38e8458ef1fc6de7f9038c32b31d58ecfeb83cce399d212079b3fb10': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '28b2c47947ef00f03eeb3b569db7c89488ac9e22712e5c72373d19033aa4fd24': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '2af60ce47149ca4c1cb7f29627a16695c047f44fd87ac1de932ec2b63d0d25fe': (
        'debt:badge-threshold-unavailable'
    ),
    '32cab7325fba8b2f585fc0214ccf345bbf32b0ed4dafab55e94022336f809cba': (
        'debt:badge-preflight-readiness'
    ),
    '346b26c59bc4ca63a09e51cea968753acd54f1a407b731b89bc5b11a5e02d599': (
        'benign:transport_or_runtime_health'
    ),
    '34c659f2601b1ddfbeab58c9d8140b87f71dd33297e81ee79a5d20d69f97d8be': (
        'debt:badge-compound-decision-grade'
    ),
    '377c1bb5561cd4fef5e2d91c14a12376aac3958f9d8aedaabbacfd4ae8bfec94': (
        'debt:badge-decision-confidence'
    ),
    '3823875dc79983dac784b51fe1932918d182d7b8546e1dca9db7c9809f8b435c': (
        'debt:badge-explainability-governance-counts'
    ),
    '3d35cd0642bc6151a02491b8f39576e526b9bdbc32b954f715d12f2490b47ff3': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '3da0a4081081e0d98676b5857cc23316a01eb91b4ad3042e154ff6bf73edf38f': (
        'debt:badge-evidence-source-freshness'
    ),
    '3e2dac1a9f9315caf321dc572ef4cd24810ae15b17ba138e6ced1afcd4a58fd6': (
        'debt:badge-compound-decision-grade'
    ),
    '406d88d51302590ea467bc8a6f1d36422bb080b18c1cb794b88c2bbd3d17ba6d': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '41847e62e0cb802532dad96b457939401e6e772a59acf0a343dc86da0873ffe5': (
        'benign:layout_or_counts'
    ),
    '435f0224f0d2a9d5eba9f709f777adacf65dd28d1c36d39f4f702e5509a64452': (
        'debt:badge-compound-decision-grade'
    ),
    '45655bebe9f1cc0ac150c68901386e1c8feb554108e278612654a4eff4b23fe5': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '4681f7d7a6a1febf2badb65da22df140fae88ba3beef9313d8240b532c161b6e': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '47e551b9d6e8882de20bfd67eb14f852149d20872aa5d9d6834060afc2a25866': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '4824d5e19c44105391522152d9bd9febfe0327fd34e6c9485f4d215c99e5c394': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '489584ca817c00d7766e9d474efd1ee37d3ae7335b1a19f41f2918042e5cfb69': (
        'debt:badge-control-approval-quality'
    ),
    '4966df28f2ae3778e52ac1226bded6b2b94a35c845a6b5e0dd729106e5f09acb': (
        'debt:badge-control-approval-quality'
    ),
    '4a079c0100a0b88e5a4cff84538e1fe187b266b842a7600660ea8cd692f86bda': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '4b0ca289239f6cb5cca22029afb268c85bf71eb90f73dae0f4a70ed2b8394cb1': (
        'benign:interaction_or_editor_state'
    ),
    '4b6cc6e1e45662b2e66cdbaacb3dcb3913ba2eac1ca4931d3847fac9a88c3e65': (
        'debt:badge-artifact-pipeline-decision-grade'
    ),
    '4d4cb2de5e3b09fe879fe2fabf09e233f9885dcfdaad158796ac4726109c5151': (
        'benign:layout_or_counts'
    ),
    '5684c71e7fde2485d3193d42e95f3e84732ac3cacc9c63fcbf38d54d3dc7186c': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '575992477f68b27fab1317f1688153b5afaced24c268c22dd2fd2b6f8c49ec76': (
        'debt:badge-evidence-source-freshness'
    ),
    '5796af5c0c00e3724ae4e0f5a21ae84464d4c8f8c8e85dc3fb9afdd03536fbc6': (
        'debt:badge-operator-blocker-overridability'
    ),
    '59b6a960611036630340cfdbdeb67c09a0b0bc2fe0d1670fe9be49d0ac386054': (
        'benign:interaction_or_editor_state'
    ),
    '5d069598ed2432ba1300d23dbf64545fdcdb1b00db025ba683c40b395882c7e9': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '5eccfc73c26b6c85df52cff3c0843e498d1c2a0b924204804c5aad9de3196ba1': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '60b71e5d2856a03dc8e9d8873e20f86b0cfcf623f4c9bcaacdb45c8048c0364c': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '614a98dc9a95cdaed03c5dfba1b519e12b58af700bf5a812e0a1aa7f582871cb': (
        'benign:layout_or_counts'
    ),
    '662b0fc3606167f10f68500739758dd6e7b7ecb8f96db7859b9e1f8d0c0546d1': (
        'benign:interaction_or_editor_state'
    ),
    '66a00026342faf1877fa8ddb5128cd33a7b369884dfe64ae18ee237560899b15': (
        'benign:layout_or_counts'
    ),
    '6ac80574002dfaad6ad5d921827e753111611f66ea6a0b7a7cce0c1b7ba96216': (
        'benign:layout_or_counts'
    ),
    '71ad7ea43a1e8dc3e3df4f67f00cc4fad983b2b6b7a0acdfc6db3daaccd8aa28': (
        'debt:badge-control-approval-quality'
    ),
    '743515ddee3a1654cf2284926e6abbd7797ef5b3ae505e2f94006d3e9ffed683': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '775183902635829ee7a634e09e77c411ad11cbe0cfff43ee743cebaf17288e25': (
        'debt:badge-preflight-readiness'
    ),
    '7752dd623b2b966fc992e43150813ae337e1667dcb2a75f1ae7e52d294655317': (
        'debt:badge-uncertainty-dispute'
    ),
    '77d4937a8a4ae3861a3d7ca0d409f1dcb5357b59fed592b6f1da55998c74415d': (
        'debt:badge-control-approval-quality'
    ),
    '782d91933a21abe282a0b2eec316c9e5a01250ae6dd1be645f0564300544c721': (
        'benign:transport_or_runtime_health'
    ),
    '790d822d3220078d0202ff5acf18234e4989dddaa8f0763460945f568889a957': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '7b7a686875b59b4b487be6ffd6040155dbbbea162d3034ae49e8de6a81a40695': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '7cab4e047bfad3eeba1fa62f6541f93ca94f7288e36da8ad9fce0b9f9fd075a8': (
        'debt:badge-compound-decision-grade'
    ),
    '7cbd142395b58dc08a0e2bb7aae5dddee45eae6beef62c24f0fb8b4b8fae67b7': (
        'benign:layout_or_counts'
    ),
    '7d026294d7ab9b024d15f64c520125bf1a56d8546bbcc0a4c3889d11381e2e80': (
        'benign:transport_or_runtime_health'
    ),
    '7dc80a2bca0f52eabe4056572779e0d61350184ebb303f8635de3a9b462b3d6f': (
        'debt:badge-candidate-refusal-markers'
    ),
    '7df766a591cd08759ab97ce6fbf3c93b1d83d01e5e6e403886ede521aef97004': (
        'benign:transport_or_runtime_health'
    ),
    '7e370a0c39a64ebb37b0b55f2a0121ab95430348581ba3f8e30cf90887a8722c': (
        'benign:transport_or_runtime_health'
    ),
    '7f61ef5fd73fcfd0d116ed59338de06d623e58f5634b4c74151527c06a902bd6': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '89146b2b5fbfd278d218aeadc24ad53693a77af147e1086cea5b51a2511659c6': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '892350aac1cb253283d156a1952c835fc1d2a8d73327b0feea81fce21d67ad24': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '89b13db33efc33ad01d076818b832f51aed4a1a2dc5bc3465376b8ff1cc42dae': (
        'debt:badge-control-approval-quality'
    ),
    '8d1d1b0a3f1bd470d97feec2780c3f3ecace0182e30b9dc4ab6fe918eea698de': (
        'benign:layout_or_counts'
    ),
    '901d277be8ac2a458d2d05c65b606307b3c6dc64f1cf48c080f57af4b6f27500': (
        'debt:badge-public-packet-authority-framing'
    ),
    '9068a4cd4f2597a561b3ee5e9cb81493c299d6a9ac44a7c39f05f4c336cf42b0': (
        'benign:transport_or_runtime_health'
    ),
    '9356fe6a3c0dee6467263ab8bf82f01253fb3629c7090a4e14277418cfc96fe6': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '9374faf00f67a0c3d645b9171576544ef88904aee1f831147de0b1f1e0572e55': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '94f7d09333cadd11a89176ef32d1646677e0070113e346a24bcf0e2f21e29d20': (
        'benign:layout_or_counts'
    ),
    '95a566e23d8a67c3342e70696b8299ce11282524dcc512ef8f1b38a542166bb9': (
        'branded:governed_authority_purpose'
    ),
    '95aea9c66d7babdca5ee9911a0db61b65d7d62614effac90dbf4478aa4b77bff': (
        'debt:badge-projection-source-freshness'
    ),
    '997f7c5ee2d23388fecbe89b4b0248095e86078fb8902768f3ee8f2b647fa2bb': (
        'benign:transport_or_runtime_health'
    ),
    '999dfc41d8905bc8fb950ce74afe4ff73d2caa9e9d1144401dd7adc0e488e37a': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '9b58b688994af67d93522e5dadaef6b0f2df21b8efc7ff8633e86db147099413': (
        'debt:badge-control-approval-quality'
    ),
    '9e5c541d557ae597994e067895ef46cc5c8106605e12517533c1ef4277c4db42': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    '9f1248b9bc7ee9c7a669e91b3ab6a03a428cc9e442163b832d7daa0fd1a700e7': (
        'debt:badge-artifact-pipeline-decision-grade'
    ),
    'a178781eec2205bb210feae1963866ddbebbc903e5b167439d795f47a47cd1ef': (
        'debt:badge-negative-certificate-blocker'
    ),
    'a39decd55a70a0982f1206d37466ed416d440f2fae951c3f6026add2f89ddfd8': (
        'benign:transport_or_runtime_health'
    ),
    'a42bc462f389e95b1711b2bd8c2d65c7efe1d62adecff77803629d81ae2c7c72': (
        'debt:badge-preflight-readiness'
    ),
    'a4a0f209ac5afc0587dbeec512266e6543cc61ba7e05f95e5b88ad141c01f9ed': (
        'debt:badge-evidence-source-freshness'
    ),
    'a608cbead8d75af67ec3a67b1bffcafec43289a959882c3f7ff1f08b943a4ef2': (
        'benign:layout_or_counts'
    ),
    'a707876130fc42b9006569b81f1f191de061ba6c2d9e00218e130c5688e3588e': (
        'benign:interaction_or_editor_state'
    ),
    'b002b5f620661bc50ef765de2a66149010e584f39eb810139e8d2441898eaacb': (
        'benign:interaction_or_editor_state'
    ),
    'b22524f2bb0c743cad0ba903c0913378f1755770798e5296e1eb2fd290a44a96': (
        'debt:badge-bureaucratic-legal-review'
    ),
    'b4ca75d2e9ab64059d514160e709e532f1c9033afba163d5e387bdb902d205a6': (
        'benign:transport_or_runtime_health'
    ),
    'b6ed98bcceca5eb3659f89e979641aaedbedbc1a7d48462b820c2ecb4b6911ec': (
        'debt:badge-candidate-refusal-markers'
    ),
    'b849a709f7783feecf45e635476c00aae9859d9a207c6cfa611a5113ce5b785a': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    'b8956759f3667ee4a2aab6f14ff3f9633530ce94bad4c5741758dbf1872f4131': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    'b8a7958e5eadceb9bb9ed7b720e1a4efb9a20bd8bced7dfdea519b92eaf82dca': (
        'debt:badge-explainability-governance-counts'
    ),
    'ba194a850616423573ab6ded36d2839fc80ae0470c30f57438a447f4232a4d41': (
        'benign:layout_or_counts'
    ),
    'ba344f7d265fd1539ac0fb5435a9f53d1caf848e8f1d452f54f90fb31097ef66': (
        'benign:layout_or_counts'
    ),
    'bbfc4140d1b606629556acde90334230a32a304f848211c89f60b73c6bd19947': (
        'debt:badge-governance-issue-severity'
    ),
    'bdf81e235a4ca11b7864dc6ecdd2284cbe034374693508f633cb85a9761eb6df': (
        'benign:transport_or_runtime_health'
    ),
    'bee1d8b47272f2e55577d8bd97988f38cee5f6857811e69b12d4c06d7545457a': (
        'debt:badge-public-anti-authority-role'
    ),
    'c189d4abe2d873e07f6be8e26b018f8d6d89469e72303dfceb0257e6e81fbf1a': (
        'debt:badge-run-deck-authority-summary'
    ),
    'c1c1c5396f7e6e331fd35de27613fac55a01597ec02e48a0c0fe7d37b229e047': (
        'benign:transport_or_runtime_health'
    ),
    'c21834b2fafddae48203bb9f1d73a8bffd39ccb98d63b23da53ba610eec8131c': (
        'debt:badge-comparability'
    ),
    'c240d2feaa07748f063fcff49d11df7617c812f95f3341136ca14d54f644c66b': (
        'benign:transport_or_runtime_health'
    ),
    'c46e2809d8f349d9518a86fe0f8c33df00e393dc7cd50f048fc7d9455a95eeba': (
        'benign:transport_or_runtime_health'
    ),
    'c614d3390a9d679fbe9253314cbd5f1a18b0613411afdb5e3d550db91252b5c6': (
        'branded:authority_presentation'
    ),
    'c7112bfb817734b2a54a7d55cdb9ad540842a4befcd49b49e8c12863a66047e8': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    'c81aad6b01055c35286a42a8bfdc07cf2223a8c47721aa6a1eaeaaf5b52bbb28': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    'cba8b385d57d853f1a0aeed9b9fd8731925269cb37a52aeb62005831353f482c': (
        'benign:layout_or_counts'
    ),
    'cc2bd39aaf90f8648705a1f6490ebf6cf38639a5a6096b1d5466a6e3e6d1f3d8': (
        'debt:badge-control-approval-quality'
    ),
    'ce1071346d9f93620cad1b88481b396016a563d8ccad39f58d2853be27d960ea': (
        'benign:layout_or_counts'
    ),
    'cef8147b083b7868c257481362ce5759966736f14fe65cd9f764ddee809e95ea': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    'cf40b1db383289a0e350568c515e85540ceef41a10c87b9c6b03a38c1ddd1657': (
        'debt:badge-public-integrity-result'
    ),
    'd1cf53e72c35bc04a947b651a2afae3efbb7d3d0261dff7aa63aa0ad705bd622': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    'd3597f124b355ae0df1aba078fe15dcbfc1eb5273d91497ee5dac0c3a10fa36e': (
        'benign:interaction_or_editor_state'
    ),
    'd5175929f2fea0f9bf06ab5951a76e03d416363447a01b1449ff1c0f04fd5d69': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    'd55790cad1c256c2c84508b5044b318ce50a87c809a16153b95de4aa1006075f': (
        'benign:transport_or_runtime_health'
    ),
    'd6e518e4dcafece66b74ce39b0d7cffb9ef46e95722e93ca7a37047f5b2f903a': (
        'debt:badge-governance-issue-severity'
    ),
    'd95f9d9d1dfd718118166a3d0a1fef3cfcefa60c5483c6d303ba303a61ac7659': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    'dbe9710ceb60817af97733abdfa27ca081c78b89a98e2242ffc4f6166567e256': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    'dfc72b6a2459a5f1bbae0f083d12aa72bfbd5bf7fbc428729b36504914a27c71': (
        'benign:layout_or_counts'
    ),
    'e1dc361da1a68012e234580fa349e121cdbf5dc50539f79e6c5e163a3ec62b50': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    'e207cfa4958f3074a81ab79b4964b8590be8beef112d00da0cd7955daa5f053a': (
        'benign:layout_or_counts'
    ),
    'e3555ae77473368474ac2aecf962494ce2e015bb56abaf84ad068b5adc37068a': (
        'benign:interaction_or_editor_state'
    ),
    'e4dd773e764fec196875160e57f6b310dbf2813075a33e9265eeb980262ef55d': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    'e8cf63710e8b312c6a9698070215a3d80fd58936593857124775f944ee4b4f27': (
        'benign:interaction_or_editor_state'
    ),
    'ec040ce3c17b4c38911f63c37a44188fa51e1415c9063352a3a46dc2f8cd734d': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    'eda6e6440c411b1ff4b59c9dd5597e500cd4426a31eddae9b46cc21f0eb636f8': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    'ee0b13c84383978509b3e3ec3504eb334945728b1ccee816e9ba13615ba68dd6': (
        'debt:badge-candidate-declared-authority-purpose'
    ),
    'eeab67da3dac0589720725a171123edeb49c68d05982622c9c36c9b06cc7c4a7': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    'eef12bc2ad51233243467d1e006c5a973e0fa138838dffc80cfe3e533ce7afc5': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    'ef1118d17b97434338471b627d65ba07d0091fe9f064ecb5a5b5c04b71c5a714': (
        'benign:interaction_or_editor_state'
    ),
    'f0d793a57b01628de090845cb7c5822c23e9f3eccae704bc732c2d5644b22433': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    'f429bd648712b69892f15f0815570e349ba93123e3c1689fcc7e8e21b1a39e47': (
        'benign:interaction_or_editor_state'
    ),
    'f46d2b5c605e3c5ab6acab65873537121df8cacb43228f16e53a000c97ec0684': (
        'benign:transport_or_runtime_health'
    ),
    'f4d4f3e59310e146c58a0ca3952caab54ef348745db6044d0097138675dd94ba': (
        'debt:badge-control-approval-quality'
    ),
    'f83591094c3b0059152f1882dc77da6851a0463478b16aa4748d05face2ec690': (
        'benign:transport_or_runtime_health'
    ),
    'f932043880d8e07b0d22732d16690d159f803a03ed23d24b9543ad412f443f8f': (
        'debt:badge-public-integrity-result'
    ),
    'f9376c6dc6670e77368e91b72ef7de90fd69f4b5290e4352c4a7dbea5d9a00dc': (
        'debt:badge-review-required-aggregate'
    ),
    'f99e0acb8cfd2e2cb117f0f4822ca0c0dde856f03f1f4d629959614e86bf9889': (
        'debt:badge-run-deck-authority-summary'
    ),
    'fb60590aea23ce4d4a823d3cf19aea558f5b666e86029388d52469f5f5739641': (
        'benign:interaction_or_editor_state'
    ),
    'fbb881aadd093a5e283964b7d4b4c1d233d7e1017887fb875d1622ecd2026235': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    'fc595d1619d1ed3590dcdf87d110fe2e4dc88a0193f018555f9eb3148bde68e2': (
        'benign:layout_or_counts'
    ),
    'feae06fefd2cab14a9599492d36ddf16213e3999dacbfa716ebeec97085618fb': (
        'benign:workflow_or_lifecycle_display_without_terminality_inference'
    ),
    'ff08cad30b4d331f3ba7cfb3757d527f2763dff5608e03f2230e6f4e3c1440b4': (
        'debt:badge-control-approval-quality'
    ),
    '1af359393d833cb5ead635d9f8e8442e724e75825ae5a8895f2b8e572244e3b2': (
        'benign:opaque_metadata_or_taxonomy'
    ),
    '3f6aa01ff891586e321a52eb178b2257fffbd55d0fe678d3d9f730ec63d60cc2': (
        'debt:badge-governed-projection-availability'
    ),
    'ba589be6170116aa03e25219cdb55b3c8718b77a3d7090d8ed25da799505eabd': (
        'debt:badge-governed-projection-availability'
    ),
}

FROZEN_AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS: dict[
    str, list[dict[str, str]]
] = {
    '06aa52447c49bbdd19d77123ae8a5a3313abd7a0a8226976da55a52915b8fe49': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-card-verdict',
            'role': 'consumer',
        },
    ],
    '090221c80046c9557a9424e0098ed8c01eaa9621b0a6f99f41d47e6f292da42a': [
        {
            'classification': 'benign:interaction_state',
            'descriptor_id': 'prop-review-presence-status',
            'role': 'consumer',
        },
    ],
    '0a9923c0cfd7cb57b27f5bacf64bac468e5862621c904335b290a17e61aa6547': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-counterfactual-status',
            'role': 'consumer',
        },
    ],
    '0e44a93350c9b74533e5905e633c97892b6e4db719cb24df3aef7ea2bbce2964': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-lineage-freshness-cue',
            'role': 'consumer',
        },
    ],
    '1288071d7e0ac163c12ce6aa1a20c20f589cbea5e2c433c37011760c01801a4a': [
        {
            'classification': 'branded:governed_authority_purpose',
            'descriptor_id': 'prop-envelope-authority-purpose',
            'role': 'consumer',
        },
    ],
    '16eb7fca7159f7309d9753a11f1b620f29fcd51b9b4301c8dfbb25a239079ab6': [
        {
            'classification': 'branded:authority_presentation',
            'descriptor_id': 'prop-authority-badge-presentation',
            'role': 'component_declaration',
        },
    ],
    '1908e4138916f64036152bf0f1aad44c6a3b305019545811e2fd330d6abfcc41': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-explainability-verdict',
            'role': 'consumer',
        },
    ],
    '19ba562d4caaa193b36eb258135bc8eedefa22de9a825e1230b7e397b9bc777a': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-verification-status-cue',
            'role': 'consumer',
        },
    ],
    '22ce2429b6954c1461643264ddeb56ea9b906a4b4c7baa61513d0db4818a9d5c': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-dispute-status',
            'role': 'consumer',
        },
    ],
    '2539f0dd770d4d81ed7eac41b8659198913e28f7433f2a126d07908aa3f41a55': [
        {
            'classification': 'benign:interaction_state',
            'descriptor_id': 'prop-review-presence-status',
            'role': 'prop_declaration',
        },
    ],
    '28451c7385b5593edfd0ac17602ed328120a4949c1a6410d9cb31a3367a773bb': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-data-freshness',
            'role': 'prop_declaration',
        },
    ],
    '2d62ca48a2d4a778b23e7a62ae53dee274c480cacff2cde588352a70e5c46d1c': [
        {
            'classification': 'benign:layout_accent',
            'descriptor_id': 'prop-composer-summary-tone',
            'role': 'component_declaration',
        },
    ],
    '3235dc9058cd679aab28663d8ef6e40fd690dba5931c4222d3c750e895090fdc': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-control-approval-readiness',
            'role': 'prop_declaration',
        },
    ],
    '345048647f2c38a7b4c40150a4f6cf8a157750e34a2313939da45a3bcc3fc03b': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-counterfactual-status',
            'role': 'component_declaration',
        },
    ],
    '3508cd57a8aa6a4eed2f965c15224b54f17b739fa262e5e96c3247b3de0aee5f': [
        {
            'classification': 'benign:layout_accent',
            'descriptor_id': 'prop-composer-summary-tone',
            'role': 'consumer',
        },
    ],
    '39f8c143570efef26b5c310b1bf429389358d39fe5bf936a40c19ee6c7211c79': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-explainability-verdict',
            'role': 'component_declaration',
        },
    ],
    '45fb2442e80045b23fdac4889b002440759292449e536cd2995b84bf67fa5893': [
        {
            'classification': 'benign:captured_quantity',
            'descriptor_id': 'prop-authored-text-confidence',
            'role': 'component_declaration',
        },
    ],
    '4626948f8965be6e9d6feb132e399319d02a9ab5c07ff4eb2e04fb977cdf9fa2': [
        {
            'classification': 'benign:layout_accent',
            'descriptor_id': 'prop-form-section-tone',
            'role': 'component_declaration',
        },
    ],
    '463bfc23955e33fcf61719c3b4510aa516bcae5e1d025ad74596bff687bc2d37': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-verification-status-icon-tone',
            'role': 'component_declaration',
        },
    ],
    '47120da814a4f5702cf969d1779626ce434e42c7ae8d22ed96c2da483f867590': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-explainability-verdict',
            'role': 'prop_declaration',
        },
    ],
    '60f1705ce16da1d211d4bd2c9291a0770773e0295f67b15aa375f9113022247e': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-grade-presentation',
            'role': 'component_declaration',
        },
    ],
    '6396aaba2a2937fd48c9bc99e4834eaa06c4122dd0e0162a9f9ba31af4e2d6a8': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-control-approval-readiness',
            'role': 'consumer',
        },
    ],
    '68ad2101e3f8b279cb6d41f7fb1ae93e5767fecf714e9db9e427b226d8454f6f': [
        {
            'classification': 'benign:responsive_layout',
            'descriptor_id': 'prop-segmented-control-tone',
            'role': 'prop_declaration',
        },
    ],
    '712710c5c423a0ffc5e2f1567cf5332bb8fcae73a1e15f0495d3312d0a1eb5de': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-grade-presentation',
            'role': 'consumer',
        },
    ],
    '71a80646a121675e49570c8c85fa30ffdd40bdf3846ffb245aa265071b73f1c5': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-data-freshness',
            'role': 'component_declaration',
        },
    ],
    '73cf45800d9bbc0e5781565dbbc6ee5de54c0c6b48682c33666e50e8686f8c7b': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-grade-presentation',
            'role': 'prop_declaration',
        },
    ],
    '76a74cb838945515d42022bddecafeb70cc1adc5f2e9334adddb61eb208352ca': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-grade-presentation',
            'role': 'consumer',
        },
    ],
    '782ed9f3d4c893ff5e9640b2c420cb48a2d08cf8e28d60740bd0c63f3039e462': [
        {
            'classification': 'benign:layout_accent',
            'descriptor_id': 'prop-form-section-tone',
            'role': 'consumer',
        },
    ],
    '785fc2a4aeab96bd67704104f7dbc63d5693438f9d48a63afe9d1ba50477256d': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-grade-presentation',
            'role': 'consumer',
        },
    ],
    '7967b768451295aab7bb93830edce43a8605903a6e00fdae468919ccb340c211': [
        {
            'classification': 'benign:layout_accent',
            'descriptor_id': 'prop-form-section-tone',
            'role': 'consumer',
        },
    ],
    '7a76b59f3a814dc6f6b1f9f887eb4b69416f0878a7af3c735f552d937fdb6823': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-verification-status-cue',
            'role': 'prop_declaration',
        },
    ],
    '831ce02647e1042330f85888d1569f0325a235e7e9ce138a03cbfa58f85e8fe7': [
        {
            'classification': 'benign:layout_accent',
            'descriptor_id': 'prop-composer-summary-tone',
            'role': 'prop_declaration',
        },
    ],
    '88061a949593f884d5bef7b9384c644d2c5c7d5d953e04413936be6c0f3a18a8': [
        {
            'classification': 'branded:authority_presentation',
            'descriptor_id': 'prop-authority-badge-presentation',
            'role': 'consumer',
        },
    ],
    '89f4504a2816c5af91a874a64d8117379b47e931e6313d226171a70f1f953413': [
        {
            'classification': 'benign:responsive_layout',
            'descriptor_id': 'prop-segmented-control-tone',
            'role': 'component_declaration',
        },
    ],
    '8a560a599792148ea45043a3e13200ca36ab8f47756a677eb1eaa2ef899a7d19': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-card-confidence',
            'role': 'prop_declaration',
        },
    ],
    '8bc040f4b701b7f4945431070d65f56529c55eb6f832d094bf116f2083689c5f': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-verification-status-cue',
            'role': 'component_declaration',
        },
    ],
    '9b0285075c32d8b904ad899c523bfd5dddde9eaa78876dec98ba96b57be00dbd': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-dispute-status',
            'role': 'prop_declaration',
        },
    ],
    'a07acb5b94cfdd350caf61f450240bda7f814c1faa029785290c9c58b47056d6': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-counterfactual-status',
            'role': 'consumer',
        },
    ],
    'a21ca9ee9373c8c076d703502dcb653879d7a6ce910e3f0e3dff896d217eafd8': [
        {
            'classification': 'benign:responsive_layout',
            'descriptor_id': 'prop-segmented-control-tone',
            'role': 'consumer',
        },
    ],
    'a87cba5c1e6540ca2bc33b6ee9a169a8fcd8fad7bf460f81d813944814ecbe84': [
        {
            'classification': 'branded:authority_presentation',
            'descriptor_id': 'prop-authority-badge-presentation',
            'role': 'consumer',
        },
    ],
    'a9a606e66e7adf776835a8a41bf8968446e341b88dfd3bed962660e5519f0b0e': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-card-verdict',
            'role': 'prop_declaration',
        },
    ],
    'b0f22a17ed4d8431f2c8e16579664f17c226202b1a9cf742a3de4fa981a440eb': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-dispute-status',
            'role': 'component_declaration',
        },
    ],
    'b1a02625d2fd21109e548cac22c0714690f5803eb15cc7b7be91e7db1f792048': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-verification-status-icon-tone',
            'role': 'consumer',
        },
    ],
    'b1e30068cb924fa281fed1ac8005603790672b75c00733847d74c8ca637a704f': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-card-verdict',
            'role': 'consumer',
        },
    ],
    'b6a1ef787665b777d6a4a7e18fdca654b493d6a8a43473a4d33756514a1e64f1': [
        {
            'classification': 'benign:layout_accent',
            'descriptor_id': 'prop-form-section-tone',
            'role': 'prop_declaration',
        },
    ],
    'b7b31de2e1cae02214b759a148df24f4a5357909c096c7ee9dab89cd3cc31ec4': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-grade-presentation',
            'role': 'consumer',
        },
    ],
    'bba89136665934edc4fb94e1e2c0becd1a0560553b6ed11486d00a5ae512e931': [
        {
            'classification': 'benign:interaction_state',
            'descriptor_id': 'prop-review-presence-status',
            'role': 'component_declaration',
        },
    ],
    'c4695dc59b4f9cbfc62344f12d91f50ab9c0042557aed065d345f054c4bf44e0': [
        {
            'classification': 'benign:captured_quantity',
            'descriptor_id': 'prop-authored-text-confidence',
            'role': 'consumer',
        },
    ],
    'c8ea08d12ba9b28b1cdfb0f1ed2d1aa2f87913b558025eb8e3448f41dd5888fa': [
        {
            'classification': 'branded:governed_authority_purpose',
            'descriptor_id': 'prop-envelope-authority-purpose',
            'role': 'component_declaration',
        },
    ],
    'cba019c47cf0748e39a681763c7d228872e1f3e33726c182359faad876a740ff': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-dispute-status',
            'role': 'consumer',
        },
    ],
    'd13b77727ec6e59051fd01de3d2595381d08ab8a5753470173f4dca54e913f6b': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-lineage-freshness-cue',
            'role': 'prop_declaration',
        },
    ],
    'd488da2243cfb0c12b495bfb8becb25dbaf50f1d03f853aaddf9e7530a52495a': [
        {
            'classification': 'branded:governed_authority_purpose',
            'descriptor_id': 'prop-envelope-authority-purpose',
            'role': 'prop_declaration',
        },
    ],
    'd6903156024e582887e0992f164d9fa191eb57d44ccb412655aec1a050ca05b8': [
        {
            'classification': 'benign:interaction_state',
            'descriptor_id': 'prop-review-presence-status',
            'role': 'consumer',
        },
    ],
    'd76cf4788345fad84023b91ef225308c43aecf68e6b58f9eb2569fdbd07e9a77': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-lineage-freshness-cue',
            'role': 'component_declaration',
        },
    ],
    'd9f1be34765232337b7e2075e012450b6474312bd313b4e3609de5ddf4488e89': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-card-confidence',
            'role': 'consumer',
        },
    ],
    'daa7db05ca9b71c307935c4f074b1d12df0dc02856ca5292b60bd1824a094230': [
        {
            'classification': 'branded:authority_presentation',
            'descriptor_id': 'prop-authority-badge-presentation',
            'role': 'prop_declaration',
        },
    ],
    'ddb70bb5bc1bb2dc30cac27c2428930e5c95c973fc5064de6c01ecb061ed1950': [
        {
            'classification': 'benign:captured_quantity',
            'descriptor_id': 'prop-authored-text-confidence',
            'role': 'consumer',
        },
    ],
    'e5cc3356ae2208fb98c4b1cdfa1d0d37f11c7e933666dc45e0098666561e14d3': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-counterfactual-status',
            'role': 'consumer',
        },
    ],
    'ea3c053f9dddfa174cd58f96f0b08967fe93e3465d82fef26c146a11f246ff9d': [
        {
            'classification': 'branded:authority_presentation',
            'descriptor_id': 'prop-authority-badge-presentation',
            'role': 'consumer',
        },
    ],
    'ead85722c60492a096a673bb40f117a9798ac462c647086ce7990f60e339f65e': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-verification-status-icon-tone',
            'role': 'prop_declaration',
        },
    ],
    'ed68a06d959bbc1db946cb34228ca88a11a8bb2a44658dbf19506ed94e5804d9': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-counterfactual-status',
            'role': 'prop_declaration',
        },
    ],
    'ef2b25e842386c37d954cb282e8d2a14cb69b22cdb689c4a273de5cd35d80911': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-control-approval-readiness',
            'role': 'component_declaration',
        },
    ],
    '0f083eca94d56e8a79548b996eb3f1d709a2f67b00548bf3c72f40080b815bed': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-data-freshness',
            'role': 'consumer',
        },
    ],
    'fb7a63d86c79d996df5f71c0611b6b7bf44848a6fc0838fb96e7dd371c28e3b2': [
        {
            'classification': 'benign:captured_quantity',
            'descriptor_id': 'prop-authored-text-confidence',
            'role': 'prop_declaration',
        },
    ],
    'fe5c1e593fa09b93ff37f01f2789d2197faa2f053ac2fc01b68493c20b29bd40': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-card-verdict',
            'role': 'component_declaration',
        },
        {
            'classification': 'debt',
            'descriptor_id': 'prop-decision-card-confidence',
            'role': 'component_declaration',
        },
    ],
}
# C21B_FROZEN_AUTHORITY_IDENTITIES_END

DS8_REMOVED_AUTHORITY_BADGE_IDENTITIES = frozenset(
    {
        "32cab7325fba8b2f585fc0214ccf345bbf32b0ed4dafab55e94022336f809cba",
        "3da0a4081081e0d98676b5857cc23316a01eb91b4ad3042e154ff6bf73edf38f",
        "5684c71e7fde2485d3193d42e95f3e84732ac3cacc9c63fcbf38d54d3dc7186c",
        "575992477f68b27fab1317f1688153b5afaced24c268c22dd2fd2b6f8c49ec76",
        "775183902635829ee7a634e09e77c411ad11cbe0cfff43ee743cebaf17288e25",
        "7b7a686875b59b4b487be6ffd6040155dbbbea162d3034ae49e8de6a81a40695",
        "892350aac1cb253283d156a1952c835fc1d2a8d73327b0feea81fce21d67ad24",
        "a4a0f209ac5afc0587dbeec512266e6543cc61ba7e05f95e5b88ad141c01f9ed",
        "c240d2feaa07748f063fcff49d11df7617c812f95f3341136ca14d54f644c66b",
        "dbe9710ceb60817af97733abdfa27ca081c78b89a98e2242ffc4f6166567e256",
    }
)
DS8_ADDED_AUTHORITY_BADGE_CLASSIFICATIONS = {
    "3e7cc757db7eddb95fe154ec05b066c4cccf23a240e0943f0675a40eba9f87a4": (
        "benign:opaque_metadata_or_taxonomy"
    ),
    "4c06f4fadf11ce470b22bb90b672256d6968ba462efc0972de32570a3de34d7a": (
        "benign:workflow_or_lifecycle_display_without_terminality_inference"
    ),
    "733a0be941f37521e2e274d3ae1002cdd671f1835b931f33f4f78d7e4d9a48b9": (
        "benign:workflow_or_lifecycle_display_without_terminality_inference"
    ),
    "7b1d2e11c323bace1ce55613fb354b597bae8a240d144d85b302d0cd3b156d5a": (
        "debt:badge-preflight-readiness"
    ),
    "91670222405793ddbb75edddf1eadf419dde7e4b57aefbf01c7ae6cdce0c89a9": (
        "benign:transport_or_runtime_health"
    ),
    "c022809e1cbe4280802c442f8f3a1e5867f5dfecf68b2e57f51a7f18d64008c1": (
        "benign:workflow_or_lifecycle_display_without_terminality_inference"
    ),
    "c7099772e56dfb77319548ebdd3dd1b17f41c38fbfda1d1295cd8b5c43bd8198": (
        "debt:badge-preflight-readiness"
    ),
    "e8b7a946aac35f592f9723ee7e896716d5bed248e926322a0aedc08a271b036d": (
        "benign:workflow_or_lifecycle_display_without_terminality_inference"
    ),
}
FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS = {
    **{
        identity: classification
        for identity, classification in FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS.items()
        if identity not in DS8_REMOVED_AUTHORITY_BADGE_IDENTITIES
    },
    **DS8_ADDED_AUTHORITY_BADGE_CLASSIFICATIONS,
}

DS9_REMOVED_AUTHORITY_BADGE_IDENTITIES = frozenset(
    {
        "078599fe50e49c45b6b69803352191205b7409a7e9f382d25019887b1e56fab1",
        "0d01fe86a863e406d0bfb676b74f4637a2102952207f1721aa1be40a332cf55e",
        "14fbd20acffc634f412e1e4619831144afdf0698b8c60afa76a91ef16251f12f",
        "168d23a2e7bbd0b65d5239812cf87afad12e77f4c5ab14c8a58ec9d1d276b415",
        "3823875dc79983dac784b51fe1932918d182d7b8546e1dca9db7c9809f8b435c",
        "489584ca817c00d7766e9d474efd1ee37d3ae7335b1a19f41f2918042e5cfb69",
        "4966df28f2ae3778e52ac1226bded6b2b94a35c845a6b5e0dd729106e5f09acb",
        "71ad7ea43a1e8dc3e3df4f67f00cc4fad983b2b6b7a0acdfc6db3daaccd8aa28",
        "77d4937a8a4ae3861a3d7ca0d409f1dcb5357b59fed592b6f1da55998c74415d",
        "89b13db33efc33ad01d076818b832f51aed4a1a2dc5bc3465376b8ff1cc42dae",
        "8d1d1b0a3f1bd470d97feec2780c3f3ecace0182e30b9dc4ab6fe918eea698de",
        "9b58b688994af67d93522e5dadaef6b0f2df21b8efc7ff8633e86db147099413",
        "b22524f2bb0c743cad0ba903c0913378f1755770798e5296e1eb2fd290a44a96",
        "b4ca75d2e9ab64059d514160e709e532f1c9033afba163d5e387bdb902d205a6",
        "b8a7958e5eadceb9bb9ed7b720e1a4efb9a20bd8bced7dfdea519b92eaf82dca",
        "bbfc4140d1b606629556acde90334230a32a304f848211c89f60b73c6bd19947",
        "cc2bd39aaf90f8648705a1f6490ebf6cf38639a5a6096b1d5466a6e3e6d1f3d8",
        "d6e518e4dcafece66b74ce39b0d7cffb9ef46e95722e93ca7a37047f5b2f903a",
        "f4d4f3e59310e146c58a0ca3952caab54ef348745db6044d0097138675dd94ba",
        "f9376c6dc6670e77368e91b72ef7de90fd69f4b5290e4352c4a7dbea5d9a00dc",
        "ff08cad30b4d331f3ba7cfb3757d527f2763dff5608e03f2230e6f4e3c1440b4",
    }
)
DS9_ADDED_AUTHORITY_BADGE_CLASSIFICATIONS = {
    "04025b6bf48105eed8ea13c99dc413d3a6d6a3917d541870d6f8912f4758cbf7": (
        "branded:authority_status_presentation"
    ),
    "4f12cdfee9d341d301c7ba1a8e6bbe166667d1c9adf82c650a3d8c3b35a67efe": (
        "branded:authority_status_presentation"
    ),
    "8e09a2ca59c5c80c6d1188a4a8697877e3d8548e18ea256f9e0d3c01d44682ac": (
        "branded:authority_status_presentation"
    ),
    "d9b92336a27cee1f90a6765042ea1bda5febcc95093654f271cd1a19f6b3a767": (
        "branded:authority_status_presentation"
    ),
    "cd7f10d2c4f7fe348faf702e069a558eb9de0112132f54462100b1dd75940b3d": (
        "benign:transport_or_runtime_health"
    ),
    "7ec5da17defbdffea479ee9d86066b2fb0bf9f1a336c62873b9dcc6081d9947e": (
        "benign:transport_or_runtime_health"
    ),
    "e397caa6296a1426824057fd84d1ec20834c509d6aab426791063225c64e31eb": ("benign:layout_or_counts"),
    "fe00676ab49a1587a9e9689da3190f2c8db4913c8fa3578c43da54d8888c834e": (
        "debt:badge-review-required-aggregate"
    ),
    "9a9defa8990c1504a4e7aa76b7b265e16ac7e304ba6e719573b04277acfaec4f": (
        "debt:badge-bureaucratic-legal-review"
    ),
    "2453b5ee6ff35f5be307a4d31be26c4d819165e99cdc572f1a0848ba80241a58": (
        "debt:badge-control-approval-quality"
    ),
    "304aab74f1ed934ab1736d820e5fdddb1c58a9430c9571504a7063c88436ac7e": (
        "debt:badge-control-approval-quality"
    ),
    "9244672b0c344b0bba51e3d665ca986e41c5c8f61a08202b8a4b7479679a9823": (
        "debt:badge-control-approval-quality"
    ),
    "733902ba89957c4105f0e95e8a652c9744c9e1462a9e1c1b936aceaf3a14f4c2": (
        "debt:badge-control-approval-quality"
    ),
    "b2de49c5ca2e5e496943c35af17a47fe0cc850a34d54cc71ef914c1afefe27c2": (
        "debt:badge-control-approval-quality"
    ),
    "e33b2b38a48939e6caffc4aab37c04f6a9e38b8b9d7bfb096aaa8ce3255fa8e7": (
        "debt:badge-control-approval-quality"
    ),
    "2b1ab574b39db4736faee9298d98a381e34c95c21f05c36334464ea17f91e73f": (
        "debt:badge-control-approval-quality"
    ),
    "36ae711bb22ec6a20fb4c564aabc7278fb3bf99697095db0abf6ceb0042a30de": (
        "debt:badge-control-approval-quality"
    ),
    "e687da7f2c74cd1771dcb374fb71d0330d36a798369426add33030ed29ae1483": (
        "debt:badge-control-approval-quality"
    ),
    "6fd2a29c46c7bdb52f93face7c5560ab5dd4e1c5e38f49f01919468f3142a5c6": (
        "debt:badge-control-approval-quality"
    ),
    "203456c009ff458adbe0569074746a6ab5b6cd0096e4cb658c2bb912afdcf2ee": (
        "debt:badge-control-approval-quality"
    ),
    "5c8a75192491067d28b0fbfb83c500f1fb99552055ef425a777f7eb17b0b7fcc": (
        "debt:badge-governance-issue-severity"
    ),
    "c82c402aa4ea1090ec5c565e2435e54b3fa702c83f544a382958be1ff5b17066": (
        "debt:badge-governance-issue-severity"
    ),
    "1c0a0d455520112d27a5a13111ce2a21999d29d3fe2f0f5cd671e4e6f5047aff": (
        "debt:badge-explainability-governance-counts"
    ),
    "2f642cf73142de1b962e24381583b2bec41e202861d9cd298072574b4d36b58a": (
        "debt:badge-explainability-governance-counts"
    ),
    "576bf7f83cf3c8d713dd8cf03a8b84558074431596c86c7a1478f6ed225d63db": (
        "debt:badge-explainability-governance-counts"
    ),
}
FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS = {
    **{
        identity: classification
        for identity, classification in FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS.items()
        if identity not in DS9_REMOVED_AUTHORITY_BADGE_IDENTITIES
    },
    **DS9_ADDED_AUTHORITY_BADGE_CLASSIFICATIONS,
}

DS10_REMOVED_AUTHORITY_BADGE_IDENTITIES = frozenset(
    {
        "062c1fe3f9e5ecaa59f778b965257dbc63be53dd48f0750430b4cf02631e73e3",
        "0b4ac8ba80f99e7e9d1bff295a1829fc21accba56ddf0fee804568f642dbcebe",
        "0d02be3c6130a3b628b630687a44aa17c3758ffda106bf5ff46a74baadcc7ec4",
        "16950ecbf6fed6faf6a6d058a4e03dfc850ac9326c49df23b1ac67ec33efeb0d",
        "3e7cc757db7eddb95fe154ec05b066c4cccf23a240e0943f0675a40eba9f87a4",
        "790d822d3220078d0202ff5acf18234e4989dddaa8f0763460945f568889a957",
        "7e370a0c39a64ebb37b0b55f2a0121ab95430348581ba3f8e30cf90887a8722c",
        "91670222405793ddbb75edddf1eadf419dde7e4b57aefbf01c7ae6cdce0c89a9",
        "94f7d09333cadd11a89176ef32d1646677e0070113e346a24bcf0e2f21e29d20",
        "a608cbead8d75af67ec3a67b1bffcafec43289a959882c3f7ff1f08b943a4ef2",
        "c022809e1cbe4280802c442f8f3a1e5867f5dfecf68b2e57f51a7f18d64008c1",
        "e207cfa4958f3074a81ab79b4964b8590be8beef112d00da0cd7955daa5f053a",
        "e8b7a946aac35f592f9723ee7e896716d5bed248e926322a0aedc08a271b036d",
        "eef12bc2ad51233243467d1e006c5a973e0fa138838dffc80cfe3e533ce7afc5",
        "f0d793a57b01628de090845cb7c5822c23e9f3eccae704bc732c2d5644b22433",
        "dfc72b6a2459a5f1bbae0f083d12aa72bfbd5bf7fbc428729b36504914a27c71",
    }
)
DS10_ADDED_AUTHORITY_BADGE_CLASSIFICATIONS = {
    # Search completeness is producer/runtime truth, never authority.
    "9b6957580db774bf2a63b6db6cef57de5af045485a79785cef1f3ca1083157b5": (
        "benign:transport_or_runtime_health"
    ),
    # Candidate and discovery states are visibly non-terminal status clothing.
    "0fb289a129fe3608f1753e45888ab4a0b5a31db8c30370a611c33677358e414b": (
        "benign:workflow_or_lifecycle_display_without_terminality_inference"
    ),
    # Existing Evidence counts/taxonomy moved when capability chrome was removed.
    "4fc8ab35628c8dfc1ffd8aabf69100113f5322c9d2392b19054ec087cf126ae7": (
        "benign:layout_or_counts"
    ),
    "9a34a55819c6a677ec19ee1b663051b106a4417c6d62459402ffacee2deed4a9": (
        "benign:layout_or_counts"
    ),
    "b0b268ca3ec1da6900dfaccbcbea7559c4307a46098dce0d53143120eb69de5f": (
        "benign:layout_or_counts"
    ),
    "058392dec56cdc629eee230434da29b16ee3391223f4ecaabf6bcb320e6e3a24": (
        "benign:layout_or_counts"
    ),
    "a3c9dadc06d9ad78eaa25debd612b158116c643c117430b56b43acb663d02cdd": (
        "benign:opaque_metadata_or_taxonomy"
    ),
    # Platform reports a count and a candidate-grade discovery state.
    "a25ca1f34db11f34a31a59f04fb3ab601a6d9cbec3813c0f54864a8ed822006e": (
        "benign:layout_or_counts"
    ),
    "25bd9b306ea3a8e8137baff2ab495e31e7d06c4071239e4d90570f458c4d27bf": (
        "benign:workflow_or_lifecycle_display_without_terminality_inference"
    ),
    "dfc72b6a2459a5f1bbae0f083d12aa72bfbd5bf7fbc428729b36504914a27c71": (
        "benign:transport_or_runtime_health"
    ),
    # Run-detail sites retain their pre-existing non-authority classifications.
    "dbe9710ceb60817af97733abdfa27ca081c78b89a98e2242ffc4f6166567e256": (
        "benign:workflow_or_lifecycle_display_without_terminality_inference"
    ),
    "5684c71e7fde2485d3193d42e95f3e84732ac3cacc9c63fcbf38d54d3dc7186c": (
        "benign:opaque_metadata_or_taxonomy"
    ),
    "7b7a686875b59b4b487be6ffd6040155dbbbea162d3034ae49e8de6a81a40695": (
        "benign:workflow_or_lifecycle_display_without_terminality_inference"
    ),
    "c240d2feaa07748f063fcff49d11df7617c812f95f3341136ca14d54f644c66b": (
        "benign:transport_or_runtime_health"
    ),
}
FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS = {
    **{
        identity: classification
        for identity, classification in FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS.items()
        if identity not in DS10_REMOVED_AUTHORITY_BADGE_IDENTITIES
    },
    **DS10_ADDED_AUTHORITY_BADGE_CLASSIFICATIONS,
}

DS15_ADDED_AUTHORITY_BADGE_CLASSIFICATIONS = {
    # Raw authority, qualification, terminality, eligibility and cost-availability
    # clothing remains typed debt until a private issuer owns its presentation.
    "ad3a39f757d1fedf96e9ab5073019b19b9e2dcc38caf6813ed3d710d08295303": (
        "debt:badge-acquisition-boundary-status"
    ),
    "9f254fb9fb7832a512196ba07dc61ac5fb757ff6839bb82ea273b4a582f33c44": (
        "debt:badge-acquisition-boundary-status"
    ),
    "735be90e13141b7f003e7a6ec4af1b2c896a4edfacfb30cf99bf301d88b30ff8": (
        "debt:badge-acquisition-boundary-status"
    ),
    "798bad599ebe71b41bc05bc17adc43bf8891c151583c3f779c9e6ad944be5585": (
        "debt:badge-acquisition-boundary-status"
    ),
    "efb98925e5a7561c62fadfb42f9111c498f71151a7e2756d3c1177c0f7802e2b": (
        "debt:badge-acquisition-boundary-status"
    ),
    "cdce54e61af1cf1ca87b6daf260fecf57db9f283b4f4bdfc090e6189398f4aef": (
        "debt:badge-acquisition-boundary-status"
    ),
    # Timeline order, ranking disclosure, local sorting and the plan-owned gap
    # vocabulary do not carry authority or infer terminality.
    "bb9927e8f2d5a34cf61a58a7c1ed4915d6cebb880e8307ed97a6b3b65a20d247": (
        "benign:workflow_or_lifecycle_display_without_terminality_inference"
    ),
    "3ea2d651ef81f94280a96f9b5ac1da08ab0f68a5037032137d0935e1fdf7efbd": (
        "benign:opaque_metadata_or_taxonomy"
    ),
    "529e354ba61570ed09ee3f79fe302c2406eb66aedc61b625a32b9cf2f8b34887": (
        "benign:interaction_or_editor_state"
    ),
    "c70aa19e61d4a1d03270ace8db367d7d5df9a94a5c3b95f4d70d0f87010102ac": (
        "benign:opaque_metadata_or_taxonomy"
    ),
    # Connector health is runtime liveness, never admission or policy authority.
    "704142beb6972df013980e33f0356e5adab5af2d820ec06ee209755a60b905af": (
        "benign:transport_or_runtime_health"
    ),
}
FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS = {
    **FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS,
    **DS15_ADDED_AUTHORITY_BADGE_CLASSIFICATIONS,
}

DS9_REMOVED_AUTHORITY_PROP_IDENTITIES = frozenset(
    {
        "39f8c143570efef26b5c310b1bf429389358d39fe5bf936a40c19ee6c7211c79",
        "ef2b25e842386c37d954cb282e8d2a14cb69b22cdb689c4a273de5cd35d80911",
    }
)
DS9_ADDED_AUTHORITY_PROP_IDENTITIES = {
    "a744741ffdfd3f839b5cb7445ab35c347601b5da0ff8ee2584d53efb68643bbf": [
        {
            "classification": "debt",
            "descriptor_id": "prop-control-approval-readiness",
            "role": "component_declaration",
        }
    ],
    "b3656572cf8086db28db2e169bd4efd4c1172fe2857d0c59fd885bd9cb62f780": [
        {
            "classification": "debt",
            "descriptor_id": "prop-explainability-verdict",
            "role": "component_declaration",
        }
    ],
}
FROZEN_AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS = {
    **{
        identity: records
        for identity, records in FROZEN_AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS.items()
        if identity not in DS9_REMOVED_AUTHORITY_PROP_IDENTITIES
    },
    **DS9_ADDED_AUTHORITY_PROP_IDENTITIES,
}

DS11_C04_REMOVED_AUTHORITY_PROP_IDENTITIES = frozenset(
    {
        "22ce2429b6954c1461643264ddeb56ea9b906a4b4c7baa61513d0db4818a9d5c",
        "463bfc23955e33fcf61719c3b4510aa516bcae5e1d025ad74596bff687bc2d37",
        "9b0285075c32d8b904ad899c523bfd5dddde9eaa78876dec98ba96b57be00dbd",
        "b0f22a17ed4d8431f2c8e16579664f17c226202b1a9cf742a3de4fa981a440eb",
        "b1a02625d2fd21109e548cac22c0714690f5803eb15cc7b7be91e7db1f792048",
        "cba019c47cf0748e39a681763c7d228872e1f3e33726c182359faad876a740ff",
        "ead85722c60492a096a673bb40f117a9798ac462c647086ce7990f60e339f65e",
    }
)
DS11_C04_ADDED_AUTHORITY_PROP_IDENTITIES = {
    "0a8a3ec01b000614831669ae914c1a5edccf4ea75c37f82832e02797d66b52b1": [
        {
            "classification": "branded:private_trust_presentation",
            "descriptor_id": "prop-verification-status-icon-tone",
            "role": "consumer",
        }
    ],
    "267d5625d47b60b00b16ac267e4d79a1e73cf913955c79197f7a422b1e460d0a": [
        {
            "classification": "branded:private_trust_presentation",
            "descriptor_id": "prop-dispute-status",
            "role": "consumer",
        }
    ],
    "2fdb61e6682a970a6f682688386765f1ecdaa5b2fb12e113615401b235d9ca1a": [
        {
            "classification": "branded:private_trust_presentation",
            "descriptor_id": "prop-verification-status-icon-tone",
            "role": "prop_declaration",
        }
    ],
    "320b5eec8742798157650fb765b74ab9eaaa6b5662ffc837aa4dcfacf55f3e62": [
        {
            "classification": "branded:private_trust_presentation",
            "descriptor_id": "prop-dispute-status",
            "role": "consumer",
        }
    ],
    "3890eee23b0a997be2fa695690c1c1f967a98529ab93edc319d76c2268720543": [
        {
            "classification": "branded:private_trust_presentation",
            "descriptor_id": "prop-verification-status-icon-tone",
            "role": "consumer",
        }
    ],
    "4494ddc9a4a66762a9c49a37f8d00c67c19c070a140cfb2608a5963b10dc6394": [
        {
            "classification": "branded:private_trust_presentation",
            "descriptor_id": "prop-dispute-status",
            "role": "component_declaration",
        }
    ],
    "58cd81b9d47a2e08eac84129a261b0e0553b84561b96b15003b7ba9889c79cca": [
        {
            "classification": "branded:private_trust_presentation",
            "descriptor_id": "prop-dispute-status",
            "role": "prop_declaration",
        }
    ],
    "59bf8834f231993eda28f48cbb7ddb84f4137cea72bdf65a164050c3140fac65": [
        {
            "classification": "branded:private_trust_presentation",
            "descriptor_id": "prop-verification-status-icon-tone",
            "role": "consumer",
        }
    ],
    "738a7abd4f505cfc754a23924133657b698bcb67390b27bf289003848c6300f2": [
        {
            "classification": "branded:private_trust_presentation",
            "descriptor_id": "prop-verification-status-icon-tone",
            "role": "component_declaration",
        }
    ],
    "788c8feb55e510fec18bfac0d364e9317fb6a195b397831637c2ffcf12a38d44": [
        {
            "classification": "branded:private_trust_presentation",
            "descriptor_id": "prop-verification-status-icon-tone",
            "role": "consumer",
        }
    ],
    "f68fcfb550031690d602b87be888017faa6b340837e12f9a1e49b3181e45f2ff": [
        {
            "classification": "branded:private_trust_presentation",
            "descriptor_id": "prop-verification-status-icon-tone",
            "role": "consumer",
        }
    ],
}
FROZEN_AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS = {
    **{
        identity: records
        for identity, records in FROZEN_AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS.items()
        if identity not in DS11_C04_REMOVED_AUTHORITY_PROP_IDENTITIES
    },
    **DS11_C04_ADDED_AUTHORITY_PROP_IDENTITIES,
}

DS18_REMOVED_AUTHORITY_BADGE_IDENTITIES = frozenset(
    {
        "12d25f70a1e4d12752533d44a2ff623892cf8a0324712949d2fd9a114372e264",
        "28b2c47947ef00f03eeb3b569db7c89488ac9e22712e5c72373d19033aa4fd24",
        "2af60ce47149ca4c1cb7f29627a16695c047f44fd87ac1de932ec2b63d0d25fe",
        "4c06f4fadf11ce470b22bb90b672256d6968ba462efc0972de32570a3de34d7a",
        "5684c71e7fde2485d3193d42e95f3e84732ac3cacc9c63fcbf38d54d3dc7186c",
        "7b7a686875b59b4b487be6ffd6040155dbbbea162d3034ae49e8de6a81a40695",
        "ba194a850616423573ab6ded36d2839fc80ae0470c30f57438a447f4232a4d41",
        "bee1d8b47272f2e55577d8bd97988f38cee5f6857811e69b12d4c06d7545457a",
        "c240d2feaa07748f063fcff49d11df7617c812f95f3341136ca14d54f644c66b",
        "c81aad6b01055c35286a42a8bfdc07cf2223a8c47721aa6a1eaeaaf5b52bbb28",
        "d5175929f2fea0f9bf06ab5951a76e03d416363447a01b1449ff1c0f04fd5d69",
        "dbe9710ceb60817af97733abdfa27ca081c78b89a98e2242ffc4f6166567e256",
    }
)
DS18_ADDED_AUTHORITY_BADGE_CLASSIFICATIONS = {
    # Publication-packet and run-route badges keep their prior semantic classes;
    # DS18 changed the enclosing temporal composition, so their content-bound
    # identities must be re-anchored without reclassifying their authority role.
    "0575c55f6ebe5ff8826e45eb83a65a82b92643d0df52b0c463cfc5cdeed85a3f": (
        "benign:opaque_metadata_or_taxonomy"
    ),
    "271e00c65bd0dffe5bfde9bc266b3d176d4dc8a555a11d19bcd97701c57c26b1": (
        "benign:workflow_or_lifecycle_display_without_terminality_inference"
    ),
    "48afb8800a54f65740380edf689c89e85a81d0287daad6e154cace7cda5f087a": (
        "debt:badge-threshold-unavailable"
    ),
    "5168e6785fb7acaa07ea2ca55fbaa64744dbd620fc09d5bdaf5deeffa8d84449": (
        "benign:opaque_metadata_or_taxonomy"
    ),
    "7c35b64cc9ffd9a4c4550e1376dbcbdb8d7169e6288e211c18f73e91e105ad72": (
        "debt:badge-public-integrity-result"
    ),
    "925d08ec731fd751c28761936c469d90d9e24c656cea4595b74556f9dba77a46": (
        "benign:transport_or_runtime_health"
    ),
    "9a246aa9a2660efd3fcbad5b4714e770b7dadcf3ebfae8571dd298ffe65b2cbe": (
        "benign:opaque_metadata_or_taxonomy"
    ),
    "ae00515ea52ca304394195043dbc08d04b2512bbefc7b505f9d1c6d113bcf7b6": (
        "benign:layout_or_counts"
    ),
    "af58c8ec7a345c5c17f6871d8bbb21d8e3c2ff270d6de8b185efa84247fb44e0": (
        "benign:workflow_or_lifecycle_display_without_terminality_inference"
    ),
    "c29904369f531395c03515056ccec0a0fb95d9c97aadf406e697bd3a89cd5516": (
        "debt:badge-public-anti-authority-role"
    ),
    "dbc9b18cdd0f356fd4106541af1770fea4e32dd396929d37697d132cefb3146c": (
        "benign:workflow_or_lifecycle_display_without_terminality_inference"
    ),
    "e5ca0b526c7fe04b851598118f3b020ef565eba27b4dca35a0588bfad9f1fe82": (
        "benign:opaque_metadata_or_taxonomy"
    ),
}
FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS = {
    **{
        identity: classification
        for identity, classification in FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS.items()
        if identity not in DS18_REMOVED_AUTHORITY_BADGE_IDENTITIES
    },
    **DS18_ADDED_AUTHORITY_BADGE_CLASSIFICATIONS,
}

AUTHORITY_BADGE_CLASSIFICATIONS = FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS


def _frozen_authority_identity_config() -> tuple[dict[str, str], dict[str, list[dict[str, str]]]]:
    """Return the committed C21b authority keys; creation receipts cannot authorize."""
    if not FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS or not FROZEN_AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS:
        raise RuntimeError("c21b_frozen_authority_identity_literals_missing")
    return (
        FROZEN_AUTHORITY_BADGE_CLASSIFICATIONS,
        FROZEN_AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS,
    )

AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS = FROZEN_AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS


def _authority_row_semantic_value(row: Mapping[str, Any]) -> dict[str, Any]:
    """Compare authority rows without treating navigation-only nested lines as identity."""
    value = copy.deepcopy(dict(row))
    sink = value.get("authority_sink")
    if isinstance(sink, dict):
        for receipt in [sink.get("component_declaration"), sink.get("prop_declaration")]:
            if isinstance(receipt, dict):
                receipt.pop("line", None)
        for receipt in sink.get("consumer_sites", []):
            if isinstance(receipt, dict):
                receipt.pop("line", None)
        consumer_sites = sink.get("consumer_sites")
        if isinstance(consumer_sites, list):
            consumer_sites.sort(
                key=lambda receipt: json.dumps(
                    receipt,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
    return value


def _authority_presentation_rows(
    scan: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build the 40 typed debt rows from the live finite census."""
    scan = scan or _authority_presentation_scan()
    census_errors = [
        *_badge_classification_errors(scan),
        *_authority_prop_classification_errors(scan),
    ]
    if census_errors:
        raise RuntimeError(
            "authority presentation census invalid: " + ", ".join(census_errors)
        )
    prop_by_id = {
        fact["descriptorId"]: fact for fact in scan["authorityPropCensus"]
    }
    debt_badge_sites_by_group = _authority_badge_sites_by_debt_group(scan)
    rows: list[dict[str, Any]] = []
    evidence_identities = _authority_evidence_identities(scan)

    for descriptor_id, spec in sorted(AUTHORITY_PROP_CLASSIFICATIONS.items()):
        if spec["classification"] != "debt":
            continue
        fact = prop_by_id[descriptor_id]
        consumer_sites = [
            _source_receipt(
                role="consumer",
                path=str(site["path"]),
                line=int(site["line"]),
                sha256=str(site["siteSha256"]),
                site=True,
            )
            for site in fact["consumerSites"]
        ]
        finding_id = "authority-presentation-" + descriptor_id
        rows.append(
            {
                "finding_id": finding_id,
                "finding_kind": "authority_presentation_debt",
                "disposition": "rebind_pending",
                "status": "open_debt",
                "evidence_refs": [
                    AUTHORITY_PRESENTATION_PLAN_REF,
                    evidence_identities[(str(fact["componentDeclarationPath"]), int(fact["componentDeclarationLine"]), "named_declaration")],
                    *sorted(
                        {
                            evidence_identities[(str(site["path"]), int(site["line"]), "jsx_attribute")]
                            for site in fact["consumerSites"]
                        }
                    ),
                ],
                "owner_slice": spec["owner_slice"],
                "decision_date": DS5_C01A_DECISION_DATE,
                "rationale": (
                    "C01a classifies this authority-bearing prop boundary as "
                    "unbranded typed debt; its owner must replace structural "
                    "clothing with the existing private-issuer brand pattern."
                ),
                "capability_states": spec["capability_states"],
                "closure_signal": spec["closure_signal"],
                "authority_sink": {
                    "sink_kind": "prop_boundary",
                    "descriptor_id": descriptor_id,
                    "component": fact["component"],
                    "prop": fact["prop"],
                    "component_declaration": _source_receipt(
                        role="component_declaration",
                        path=str(fact["componentDeclarationPath"]),
                        line=int(fact["componentDeclarationLine"]),
                        sha256=str(fact["componentDeclarationSha256"]),
                    ),
                    "prop_declaration": _source_receipt(
                        role="prop_declaration",
                        path=str(fact["propDeclarationPath"]),
                        line=int(fact["propDeclarationLine"]),
                        sha256=str(fact["propDeclarationSha256"]),
                    ),
                    "consumer_count": len(consumer_sites),
                    "consumer_sites": consumer_sites,
                },
            }
        )

    for group_id, spec in sorted(AUTHORITY_BADGE_DEBT_SPECS.items()):
        badge_sites = debt_badge_sites_by_group[group_id]
        finding_id = "authority-presentation-" + group_id
        ds9_c07_support = finding_id in DS9_C07_AUTHORITY_FINDING_IDS
        decision_date = DS9_C07_DECISION_DATE if ds9_c07_support else DS5_C01A_DECISION_DATE
        if not badge_sites:
            rows.append(
                {
                    "finding_id": finding_id,
                    "finding_kind": "authority_presentation_debt",
                    "disposition": "rebind_pending",
                    "status": "open_debt",
                    "evidence_refs": [AUTHORITY_PRESENTATION_PLAN_REF],
                    "owner_slice": spec["owner_slice"],
                    "decision_date": decision_date,
                    "rationale": (
                        (
                            "DS9 C07 proves the direct consumer absent after "
                            "routing the supported surface through the private "
                            "issuer; producer and bridge debt remains open."
                        )
                        if ds9_c07_support
                        else (
                            "The live census establishes that this authority-debt "
                            "group has no remaining direct Badge consumer. Its "
                            "producer and bridge capability debt remains open "
                            "without preserving a stale sink."
                        )
                    ),
                    "capability_states": spec["capability_states"],
                    "closure_signal": spec["closure_signal"],
                    "authority_sink_absence": {
                        "sink_kind": "direct_badge_group",
                        "descriptor_id": group_id,
                        "consumer_count": 0,
                        "predicate_provenance": "recomputed",
                        "reason": "no_live_consumer_sites",
                    },
                }
            )
            continue
        first = badge_sites[0]
        component_identity = (
            first["component"],
            first["componentDeclarationPath"],
            first["componentDeclarationLine"],
            first["componentDeclarationSha256"],
        )
        if any(
            (
                site["component"],
                site["componentDeclarationPath"],
                site["componentDeclarationLine"],
                site["componentDeclarationSha256"],
            )
            != component_identity
            for site in badge_sites
        ):
            raise RuntimeError(f"Badge declaration identity drift: {group_id}")
        consumer_sites = [
            _source_receipt(
                role="consumer",
                path=str(site["path"]),
                line=int(site["line"]),
                sha256=str(site["siteSha256"]),
                site=True,
            )
            for site in badge_sites
        ]
        rows.append(
            {
                "finding_id": finding_id,
                "finding_kind": "authority_presentation_debt",
                "disposition": "rebind_pending",
                "status": "open_debt",
                "evidence_refs": [
                    AUTHORITY_PRESENTATION_PLAN_REF,
                    evidence_identities[(str(first["componentDeclarationPath"]), int(first["componentDeclarationLine"]), "named_declaration")],
                    *sorted(
                        {
                            evidence_identities[(str(site["path"]), int(site["line"]), "jsx_opening")]
                            for site in badge_sites
                        }
                    ),
                ],
                "owner_slice": spec["owner_slice"],
                "decision_date": decision_date,
                "rationale": (
                    (
                        "DS9 C07 routes every direct Badge consumer in this group "
                        "through one privately issued projection with explicit "
                        "runtime novelty behavior. The producer and bridge gaps "
                        "remain open under the existing owner and closure signal."
                    )
                    if ds9_c07_support
                    else (
                        "C01a classifies this direct authority-bearing Badge group "
                        "as unbranded typed debt; its owner must replace "
                        "caller-chosen clothing with the existing private-issuer "
                        "brand pattern."
                    )
                ),
                "capability_states": spec["capability_states"],
                "closure_signal": spec["closure_signal"],
                "authority_sink": {
                    "sink_kind": "direct_badge_group",
                    "descriptor_id": group_id,
                    "component": first["component"],
                    "component_declaration": _source_receipt(
                        role="component_declaration",
                        path=str(first["componentDeclarationPath"]),
                        line=int(first["componentDeclarationLine"]),
                        sha256=str(first["componentDeclarationSha256"]),
                    ),
                    "consumer_count": len(consumer_sites),
                    "consumer_sites": consumer_sites,
                },
            }
        )
    return sorted(rows, key=lambda row: row["finding_id"])


def _authority_presentation_errors(
    data: Mapping[str, Any], *, live_probes: bool = True,
    scan: Mapping[str, Any] | None = None,
) -> list[str]:
    """Bind every authority debt row byte-for-byte to its finite live census."""
    errors: list[str] = []
    stored_rows = data.get("supplemental_findings", [])
    if not isinstance(stored_rows, list):
        return ["authority_presentation_debt_invalid_container"]
    authority_scan = scan or _authority_presentation_scan()
    try:
        expected_rows = _authority_presentation_rows(authority_scan)
    except RuntimeError as exc:
        return [str(exc)]
    expected_by_id = {row["finding_id"]: row for row in expected_rows}
    stored_by_id = {
        str(row.get("finding_id")): row
        for row in stored_rows
        if isinstance(row, Mapping)
    }
    for finding_id, expected in expected_by_id.items():
        row = stored_by_id.get(finding_id)
        if row is None:
            errors.append(
                f"authority_presentation_debt_drift:{finding_id}:finding_id"
            )
            continue
        expected_value = _authority_row_semantic_value(expected)
        stored_value = _authority_row_semantic_value(row)
        for field, field_value in expected_value.items():
            if stored_value.get(field) != field_value:
                errors.append(
                    f"authority_presentation_debt_drift:{finding_id}:{field}"
                )
    for row in stored_rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("finding_kind") == "authority_presentation_debt":
            finding_id = str(row.get("finding_id", "unknown"))
            if (
                finding_id not in expected_by_id
                and finding_id not in DS11_TRUST_PRESENTATION_FINDING_IDS
            ):
                errors.append(
                    "authority_presentation_debt_descriptor_missing:" + finding_id
                )
    if live_probes:
        errors.extend(_badge_classification_errors(authority_scan))
        errors.extend(_authority_prop_classification_errors(authority_scan))
    return errors


@lru_cache(maxsize=1)
def _ds11_raw_trust_root_scan() -> dict[str, Any]:
    """Scan the retired Trust View roots through the compiler, not a text grep."""
    request = {
        "authorityPathDescriptors": _ds11_trust_presentation_path_descriptors(),
        "authorityPropDescriptors": list(DS11_RAW_TRUST_ROOT_DESCRIPTORS),
    }
    return status_checker._scan_json(
        json.dumps(request, sort_keys=True, separators=(",", ":"))
    )


def _ds11_is_production_dashboard_source(path: str) -> bool:
    """Match the complete 625-file Trust View production denominator."""
    return (
        path.startswith("apps/runtime-dashboard/src/")
        and path.endswith((".ts", ".tsx"))
        and not path.endswith(".d.ts")
        and not re.search(
            r"\.(?:a11y\.)?(?:test|spec)\.[cm]?tsx?$|\.stories\.[cm]?tsx?$",
            path,
        )
        and not ("/src/test/" in path and path.endswith(".tsx"))
    )


def _ds11_trust_presentation_semantic_errors(
    scan: Mapping[str, Any],
    *,
    raw_scan: Mapping[str, Any] | None = None,
) -> list[str]:
    """Prove the two DS11 sinks use one private, identity-backed issuer."""
    errors: list[str] = []
    facts = scan.get("authorityPropCensus")
    if not isinstance(facts, list):
        return ["ds11_trust_presentation_census_invalid"]
    observed_descriptors = {
        str(fact.get("descriptorId"))
        for fact in facts
        if isinstance(fact, Mapping)
    }
    if not DS11_TRUST_PRESENTATION_DESCRIPTOR_IDS <= observed_descriptors:
        errors.append("ds11_trust_presentation_descriptor_missing")

    path_facts = scan.get("authorityPathFiles")
    if not isinstance(path_facts, list):
        errors.append("ds11_trust_presentation_mechanism_path_census_invalid")
    else:
        production_paths = {
            str(row.get("path"))
            for row in path_facts
            if isinstance(row, Mapping)
            and _ds11_is_production_dashboard_source(str(row.get("path", "")))
        }
        if production_paths != set(DS11_C04_MECHANISM_PATHS):
            errors.append("ds11_trust_presentation_mechanism_path_drift")

    raw_scan = raw_scan or _ds11_raw_trust_root_scan()
    raw_facts = raw_scan.get("authorityPropCensus")
    if not isinstance(raw_facts, list):
        errors.append("ds11_trust_raw_root_census_invalid")
    else:
        raw_descriptor_ids = sorted(
            str(fact.get("descriptorId"))
            for fact in raw_facts
            if isinstance(fact, Mapping)
        )
        if raw_descriptor_ids:
            errors.append(
                "ds11_trust_raw_root_live:" + ",".join(raw_descriptor_ids)
            )

    issuer = scan.get("authorityIssuerFacts")
    if not isinstance(issuer, Mapping):
        return [*errors, "ds11_trust_presentation_issuer_facts_invalid"]
    modules = issuer.get("modules")
    if (
        not isinstance(modules, list)
        or len(modules) != 1
        or not isinstance(modules[0], Mapping)
        or modules[0].get("path") != DS11_TRUST_GLYPHS_PATH
        or not re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            str(modules[0].get("sourceSha256", "")),
        )
    ):
        errors.append("ds11_trust_presentation_issuer_module_drift")

    module_accesses = issuer.get("moduleAccesses")
    if not isinstance(module_accesses, list):
        errors.append("ds11_trust_presentation_module_access_census_invalid")
    elif any(
        isinstance(access, Mapping)
        and access.get("factory") == "issueTrustPresentation"
        and _ds11_is_production_dashboard_source(str(access.get("path", "")))
        for access in module_accesses
    ):
        errors.append("ds11_trust_presentation_unsafe_module_access")

    direct_calls = issuer.get("directCalls")
    if not isinstance(direct_calls, list):
        errors.append("ds11_trust_presentation_direct_call_census_invalid")
    else:
        production_callers = Counter(
            str(call.get("path"))
            for call in direct_calls
            if isinstance(call, Mapping)
            and call.get("factory") == "issueTrustPresentation"
            and _ds11_is_production_dashboard_source(str(call.get("path", "")))
        )
        if production_callers != Counter(DS11_C04_ISSUER_CALLERS):
            errors.append("ds11_trust_presentation_issuer_caller_drift")

    brands = issuer.get("brands")
    if not isinstance(brands, list) or len(brands) != 1:
        errors.append("ds11_trust_presentation_brand_cardinality")
        brand_name = None
    else:
        brand = brands[0]
        brand_name = brand.get("name") if isinstance(brand, Mapping) else None
        if (
            not isinstance(brand, Mapping)
            or brand.get("path") != DS11_TRUST_GLYPHS_PATH
            or brand.get("exported") is not False
            or not isinstance(brand_name, str)
        ):
            errors.append("ds11_trust_presentation_brand_privacy")

    factories = issuer.get("factories")
    matching_factories = [
        factory
        for factory in factories if isinstance(factory, Mapping)
        and factory.get("name") == "issueTrustPresentation"
    ] if isinstance(factories, list) else []
    if len(matching_factories) != 1:
        errors.append("ds11_trust_presentation_issuer_cardinality")
    else:
        factory = matching_factories[0]
        parameters = factory.get("parameters")
        if (
            factory.get("path") != DS11_TRUST_GLYPHS_PATH
            or factory.get("returnBrands") != [brand_name]
            or parameters
            != [
                {
                    "name": "metadata",
                    "type": "unknown",
                    "generated": False,
                    "generatedPaths": [],
                    "broadString": False,
                    "optional": False,
                    "rest": False,
                }
            ]
        ):
            errors.append("ds11_trust_presentation_issuer_contract_drift")

    stores = issuer.get("stores")
    stores_by_name = {
        str(store.get("name")): store
        for store in stores
        if isinstance(store, Mapping)
    } if isinstance(stores, list) else {}
    expected_stores = {
        "issuedTrustPresentations": {
            "kind": "WeakSet",
            "reads": [
                {
                    "function": "isIssuedTrustPresentation",
                    "method": "has",
                    "argumentParameter": "value",
                }
            ],
            "writes": [
                {"function": "issueTrustPresentation", "method": "add"}
            ],
        },
        "issuedTrustPresentationData": {
            "kind": "WeakMap",
            "reads": [
                {
                    "function": "presentTrustPresentation",
                    "method": "get",
                    "argumentParameter": "value",
                }
            ],
            "writes": [
                {"function": "issueTrustPresentation", "method": "set"}
            ],
        },
    }
    if set(stores_by_name) != set(expected_stores):
        errors.append("ds11_trust_presentation_identity_store_cardinality")
    for name, expected in expected_stores.items():
        store = stores_by_name.get(name)
        if (
            not isinstance(store, Mapping)
            or store.get("path") != DS11_TRUST_GLYPHS_PATH
            or store.get("exported") is not False
            or store.get("kind") != expected["kind"]
            or store.get("reads") != expected["reads"]
            or store.get("writes") != expected["writes"]
        ):
            errors.append("ds11_trust_presentation_identity_store_drift:" + name)

    escape_sites = scan.get("authorityEscapeSites")
    if isinstance(escape_sites, list):
        unsafe_brand_assertions = [
            site
            for site in escape_sites
            if isinstance(site, Mapping)
            and site.get("construct") in {"as_assertion", "type_assertion"}
            and site.get("target") == "TrustPresentation"
            and site.get("path") != DS11_TRUST_GLYPHS_PATH
        ]
        if unsafe_brand_assertions:
            errors.append("ds11_trust_presentation_external_brand_assertion")
    else:
        errors.append("ds11_trust_presentation_escape_census_invalid")
    return errors


def _ds11_trust_presentation_rows(
    scan: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Render the two repaired DS11 rows from compiler-resolved source facts."""
    scan = scan or _authority_presentation_scan()
    semantic_errors = _ds11_trust_presentation_semantic_errors(scan)
    if semantic_errors:
        raise RuntimeError(";".join(semantic_errors))
    facts = {
        str(fact["descriptorId"]): fact
        for fact in scan["authorityPropCensus"]
        if isinstance(fact, Mapping)
        and str(fact.get("descriptorId"))
        in DS11_TRUST_PRESENTATION_DESCRIPTOR_IDS
    }
    if set(facts) != DS11_TRUST_PRESENTATION_DESCRIPTOR_IDS:
        raise RuntimeError("ds11_trust_presentation_finding_denominator_drift")
    issuer_module = scan["authorityIssuerFacts"]["modules"][0]
    issuer_evidence_ref = (
        f"{DS11_TRUST_GLYPHS_PATH}#content-sha256="
        f"{issuer_module['sourceSha256']}"
    )
    evidence_identities = _authority_evidence_identities(scan)
    rows: list[dict[str, Any]] = []
    for descriptor_id in sorted(DS11_TRUST_PRESENTATION_DESCRIPTOR_IDS):
        fact = facts[descriptor_id]
        consumer_sites = [
            _source_receipt(
                role="consumer",
                path=str(site["path"]),
                line=int(site["line"]),
                sha256=str(site["siteSha256"]),
                site=True,
            )
            for site in fact["consumerSites"]
        ]
        rows.append(
            {
                "finding_id": "authority-presentation-" + descriptor_id,
                "finding_kind": "authority_presentation_debt",
                "disposition": "rebind_pending",
                "status": "repaired",
                "evidence_refs": [
                    "docs/plans/active/atlas-slices/DS11-trust-docs-posture.md#c04--trust-view-private-issuer-repair",
                    issuer_evidence_ref,
                    evidence_identities[
                        (
                            str(fact["componentDeclarationPath"]),
                            int(fact["componentDeclarationLine"]),
                            "named_declaration",
                        )
                    ],
                    *sorted(
                        {
                            evidence_identities[
                                (str(site["path"]), int(site["line"]), "jsx_attribute")
                            ]
                            for site in fact["consumerSites"]
                        }
                    ),
                ],
                "owner_slice": "DS11",
                "decision_date": DS11_C04_DECISION_DATE,
                "rationale": (
                    "DS11 C04 replaces the inherited caller-selected Trust View "
                    "clothing boundary with one private identity-backed issuer. "
                    "The compiler-resolved sink and consumer receipts bind the "
                    "issued presentation; raw status/tone roots are absent."
                ),
                "authority_sink": {
                    "sink_kind": "prop_boundary",
                    "descriptor_id": descriptor_id,
                    "component": fact["component"],
                    "prop": fact["prop"],
                    "component_declaration": _source_receipt(
                        role="component_declaration",
                        path=str(fact["componentDeclarationPath"]),
                        line=int(fact["componentDeclarationLine"]),
                        sha256=str(fact["componentDeclarationSha256"]),
                    ),
                    "prop_declaration": _source_receipt(
                        role="prop_declaration",
                        path=str(fact["propDeclarationPath"]),
                        line=int(fact["propDeclarationLine"]),
                        sha256=str(fact["propDeclarationSha256"]),
                    ),
                    "consumer_count": len(consumer_sites),
                    "consumer_sites": consumer_sites,
                },
            }
        )
    return sorted(rows, key=lambda row: row["finding_id"])


def _validate_ds11_trust_presentation_transition_findings(
    data: Mapping[str, Any],
    errors: list[str],
    *,
    scan: Mapping[str, Any] | None = None,
) -> None:
    """Bind only the two DS11 repaired rows to the private issuer source facts."""
    try:
        expected_rows = _ds11_trust_presentation_rows(scan)
    except RuntimeError as exc:
        errors.append("ds11_trust_presentation_source_invalid:" + str(exc))
        return
    expected_by_id = {str(row["finding_id"]): row for row in expected_rows}
    stored_rows = data.get("supplemental_findings", [])
    if not isinstance(stored_rows, list):
        errors.append("ds11_trust_presentation_invalid_container")
        return
    for finding_id in sorted(DS11_TRUST_PRESENTATION_FINDING_IDS):
        matches = [
            row
            for row in stored_rows
            if isinstance(row, Mapping) and row.get("finding_id") == finding_id
        ]
        if len(matches) != 1 or matches[0] != expected_by_id.get(finding_id):
            errors.append("ds11_trust_presentation_transition_drift:" + finding_id)

GOVERNED_DEBT_DESCRIPTORS = {
    finding_id: {
        "finding_id": finding_id,
        **copy.deepcopy(descriptor),
        "decision_date": descriptor.get("decision_date", DECISION_DATE),
    }
    for finding_id, descriptor in PRODUCER_BINDING_DEBT_DESCRIPTORS.items()
}
GOVERNED_DEBT_DESCRIPTORS.update(copy.deepcopy(INTEGRATE_DEBT_DESCRIPTORS))

C11B_QUERY_MEMORY_ROOT_ID = "cache-query-memory"
C11B_QUERY_MEMORY_SUCCESSOR_ID = "dashboard-governed-query-cache-posture"
C11B_QUERY_MEMORY_OPENING_SUCCESSOR_REFS = [
    "apps/runtime-dashboard/src/api/queryKeys.ts",
    "apps/runtime-dashboard/src/api/governedQueryPolicy.ts",
    "apps/runtime-dashboard/src/api/governedQueryPolicy.test.ts",
    "apps/runtime-dashboard/src/api/cacheDiscipline.ts",
    "apps/runtime-dashboard/src/api/cacheDiscipline.test.ts",
    "apps/runtime-dashboard/src/features/runs/api/useDepthNCycleBoardProjection.ts",
    "apps/runtime-dashboard/src/features/runs/api/useDepthNCycleBoardProjection.test.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.test.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.parity.test.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/CycleBoardConsumerCensus.test.ts",
]
DS15_QUERY_MEMORY_SUCCESSOR_REFS = [
    "apps/runtime-dashboard/src/api/queryKeys.ts",
    "apps/runtime-dashboard/src/api/governedQueryPolicy.ts",
    "apps/runtime-dashboard/src/api/governedQueryPolicy.test.ts",
    "apps/runtime-dashboard/src/api/cacheDiscipline.ts",
    "apps/runtime-dashboard/src/api/cacheDiscipline.test.ts",
    "apps/runtime-dashboard/src/api/optimistic.test.ts",
    "apps/runtime-dashboard/src/features/runs/api/useDepthNCycleBoardProjection.ts",
    "apps/runtime-dashboard/src/features/runs/api/useDepthNCycleBoardProjection.test.tsx",
    "apps/runtime-dashboard/src/features/runs/api/useAcquisitionRoutes.ts",
    "apps/runtime-dashboard/src/features/runs/api/useAcquisitionRoutes.test.tsx",
    "apps/runtime-dashboard/src/features/runs/components/CycleBoard.tsx",
    "apps/runtime-dashboard/src/features/runs/components/CycleBoard.test.tsx",
    "apps/runtime-dashboard/src/features/runs/components/AcquisitionApprovalFlow.tsx",
    "apps/runtime-dashboard/src/features/runs/components/AcquisitionApprovalFlow.test.tsx",
    "apps/runtime-dashboard/src/features/runs/components/AcquisitionApprovalFlow.a11y.test.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.test.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.parity.test.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.test.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.parity.test.tsx",
    "apps/runtime-dashboard/src/features/runs/routes/CycleBoardConsumerCensus.test.ts",
]
C11B_QUERY_MEMORY_SUCCESSOR_REFS = DS15_QUERY_MEMORY_SUCCESSOR_REFS
C11B_QUERY_MEMORY_PENDING_RATIONALE = (
    "DS1 does not record this narrow unit as implemented; C04a-R1 removes the "
    "local capability fallback and query placeholder from its CommandPalette "
    "discovery consumer, while cache-policy transition remains owned by C11/C12 "
    "without creating a parallel owner."
)
C11B_QUERY_MEMORY_OPENING_RATIONALE = (
    "C11a/C11b, C12b, and DS7 strangle the generic query-memory root through the "
    "governed-query option issuer, one representation-specific key, explicit "
    "never_cache_authority posture, and one permission-gated global Cycle Board "
    "consumer. Transaction observation time is not owner as_of, run detail neither "
    "fetches nor retains the packet, and exact response bytes remain per-request "
    "export custody only; no DS8, DS9, or DS14 semantics are claimed."
)
DS15_QUERY_MEMORY_RATIONALE = (
    "C11a/C11b, C12b, DS7, and DS15 strangle the generic query-memory root "
    "through the governed-query option issuer, depth-N and acquisition key "
    "families, explicit never_cache_authority posture, and the complete live "
    "Cycle Board, Case Workspace, and acquisition-approval consumer set. "
    "Transaction observation time is not owner as_of, exact response bytes "
    "remain per-request export custody only, and DS15's test-only positive flow "
    "does not establish production world growth; no DS8, DS9, or DS14 semantics "
    "are claimed."
)
C11B_QUERY_MEMORY_RATIONALE = DS15_QUERY_MEMORY_RATIONALE


def _json_entry_object_span(
    text: str, unit_id: str
) -> tuple[int, int, Mapping[str, Any]]:
    """Locate one root-entry object without normalizing adjacent JSON bytes."""
    needle = f'"unit_id": {json.dumps(unit_id, ensure_ascii=False)}'
    positions = [match.start() for match in re.finditer(re.escape(needle), text)]
    if len(positions) != 1:
        raise ValueError(f"root_entry_span_ambiguous:{unit_id}")
    line_start = text.rfind("    {", 0, positions[0])
    if line_start < 0:
        raise ValueError(f"root_entry_span_missing:{unit_id}")
    start = line_start + 4
    row, relative_end = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(row, Mapping) or row.get("unit_id") != unit_id:
        raise ValueError(f"root_entry_span_mismatch:{unit_id}")
    return start, start + relative_end, row


def _render_root_entry(row: Mapping[str, Any]) -> str:
    """Render one root object at the register's existing array indentation."""
    rendered = json.dumps(row, indent=2, ensure_ascii=False)
    lines = rendered.splitlines()
    return lines[0] + "\n" + "\n".join("    " + line for line in lines[1:])


def _json_top_level_object_span(text: str, key: str) -> tuple[int, int, Mapping[str, Any]]:
    """Locate one top-level object value without normalizing adjacent bytes."""
    needle = f"  {json.dumps(key, ensure_ascii=False)}: "
    positions = [match.start() for match in re.finditer(re.escape(needle), text)]
    if len(positions) != 1:
        raise ValueError(f"top_level_object_span_ambiguous:{key}")
    start = positions[0] + len(needle)
    row, relative_end = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(row, Mapping):
        raise ValueError(f"top_level_object_span_mismatch:{key}")
    return start, start + relative_end, row


def _render_top_level_object(row: Mapping[str, Any]) -> str:
    """Render one top-level object at the register's existing indentation."""
    rendered = json.dumps(row, indent=2, ensure_ascii=False)
    lines = rendered.splitlines()
    return lines[0] + "\n" + "\n".join("  " + line for line in lines[1:])


def _json_object_span_by_identity(
    text: str,
    *,
    field: str,
    value: str,
    within: tuple[int, int],
) -> tuple[int, int, Mapping[str, Any]]:
    """Locate one nested JSON object by an exact identity field and value."""
    within_start, within_end = within
    needle = f"{json.dumps(field)}: {json.dumps(value)}"
    positions = [
        match.start()
        for match in re.finditer(re.escape(needle), text[within_start:within_end])
    ]
    if len(positions) != 1:
        raise ValueError(f"json_identity_span_ambiguous:{field}:{value}")
    identity_start = within_start + positions[0]
    object_starts = [
        match.start()
        for match in re.finditer(r"\{", text[within_start:identity_start])
    ]
    for relative_start in reversed(object_starts):
        start = within_start + relative_start
        try:
            row, relative_end = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        end = start + relative_end
        if (
            end <= within_end
            and isinstance(row, Mapping)
            and row.get(field) == value
        ):
            return start, end, row
    raise ValueError(f"json_identity_object_missing:{field}:{value}")


def _json_field_value_span(
    text: str,
    *,
    field: str,
    within: tuple[int, int],
) -> tuple[int, int, Any]:
    """Locate one JSON field value inside a previously bounded object."""
    within_start, within_end = within
    needle = f"{json.dumps(field)}: "
    positions = [
        match.start()
        for match in re.finditer(re.escape(needle), text[within_start:within_end])
    ]
    if len(positions) != 1:
        raise ValueError(f"json_field_value_span_ambiguous:{field}")
    start = within_start + positions[0] + len(needle)
    value, relative_end = json.JSONDecoder().raw_decode(text[start:])
    end = start + relative_end
    if end > within_end:
        raise ValueError(f"json_field_value_span_outside_object:{field}")
    return start, end, value


def _ds9_c07_storage_target_spans(
    text: str,
) -> list[tuple[str, int, int, Any]]:
    """Locate only the four storage receipt scalars that C07 may rewrite."""
    census_start, census_end, _census = _json_top_level_object_span(
        text, "storage_construction_census"
    )
    census_bounds = (census_start, census_end)
    factory_start, factory_end, _factory = _json_object_span_by_identity(
        text,
        field="factory_site_id",
        value=DS9_C07_STORAGE_FACTORY_ID,
        within=census_bounds,
    )
    site_start, site_end, _site = _json_object_span_by_identity(
        text,
        field="site_id",
        value=DS9_C07_STORAGE_SITE_ID,
        within=census_bounds,
    )
    targets = []
    for label, field, bounds in (
        (
            "induced:storage_factory_source_fingerprint",
            "source_fingerprint",
            (factory_start, factory_end),
        ),
        (
            "induced:storage_site_source_fingerprint",
            "source_fingerprint",
            (site_start, site_end),
        ),
        (
            "induced:storage_authority_factory_receipts_sha256",
            "authority_factory_receipts_sha256",
            census_bounds,
        ),
        ("induced:storage_rows_sha256", "rows_sha256", census_bounds),
    ):
        start, end, value = _json_field_value_span(
            text,
            field=field,
            within=bounds,
        )
        targets.append((label, start, end, value))
    return sorted(targets, key=lambda item: item[1])


def _ds9_c07_storage_transition_text(text: str) -> str:
    """Re-anchor only the two C06-touched dispute source receipts and digests."""
    _start, _end, stored = _json_top_level_object_span(
        text, "storage_construction_census"
    )
    candidate = copy.deepcopy(dict(stored))
    factory_receipts = candidate.get("authority_factory_receipts")
    sites = candidate.get("sites")
    if not isinstance(factory_receipts, list) or not isinstance(sites, list):
        raise ValueError("DS9 C07 storage census container drift")
    factories = [
        row
        for row in factory_receipts
        if isinstance(row, dict) and row.get("factory_site_id") == DS9_C07_STORAGE_FACTORY_ID
    ]
    storage_sites = [
        row
        for row in sites
        if isinstance(row, dict) and row.get("site_id") == DS9_C07_STORAGE_SITE_ID
    ]
    if len(factories) != 1 or len(storage_sites) != 1:
        raise ValueError("DS9 C07 dispute storage receipt cardinality drift")
    live_source_sha256 = _sha256(REPO_ROOT / DS9_C07_STORAGE_SOURCE_PATH)
    factory_source_preimage = factories[0].get("source_fingerprint")
    site_source_preimage = storage_sites[0].get("source_fingerprint")
    opening_factory_digest = "sha256:" + _canonical_sha256(factory_receipts)
    opening_rows_digest = "sha256:" + _canonical_sha256(sites)
    for row in (*factories, *storage_sites):
        if row.get("path") != DS9_C07_STORAGE_SOURCE_PATH:
            raise ValueError("DS9 C07 dispute storage source path drift")
        if row.get("source_fingerprint") not in {
            DS9_C07_STORAGE_OPENING_SOURCE_SHA256,
            live_source_sha256,
        }:
            raise ValueError("DS9 C07 dispute storage source preimage drift")
        row["source_fingerprint"] = live_source_sha256
    candidate["authority_factory_receipts_sha256"] = "sha256:" + _canonical_sha256(factory_receipts)
    candidate["rows_sha256"] = "sha256:" + _canonical_sha256(sites)
    targets = {
        label: (start, end, value)
        for label, start, end, value in _ds9_c07_storage_target_spans(text)
    }
    expected_preimages = {
        "induced:storage_factory_source_fingerprint": factory_source_preimage,
        "induced:storage_site_source_fingerprint": site_source_preimage,
        "induced:storage_authority_factory_receipts_sha256": opening_factory_digest,
        "induced:storage_rows_sha256": opening_rows_digest,
    }
    replacements = {
        "induced:storage_factory_source_fingerprint": live_source_sha256,
        "induced:storage_site_source_fingerprint": live_source_sha256,
        "induced:storage_authority_factory_receipts_sha256": candidate[
            "authority_factory_receipts_sha256"
        ],
        "induced:storage_rows_sha256": candidate["rows_sha256"],
    }
    for label, expected in expected_preimages.items():
        if targets[label][2] != expected:
            raise ValueError(f"DS9 C07 storage scalar preimage drift:{label}")
    result = text
    for label, (start, end, _value) in sorted(
        targets.items(), key=lambda item: item[1][0], reverse=True
    ):
        result = result[:start] + json.dumps(replacements[label]) + result[end:]
    return result


def _ds9_c07_root_transition_text(text: str) -> str:
    """Adjudicate exactly 13 DS9 roots without normalizing peer bytes."""
    replacements: list[tuple[int, int, str]] = []
    for unit_id, scope in DS9_C07_ROOT_SCOPE.items():
        start, end, stored = _json_entry_object_span(text, unit_id)
        formal = DS9_C07_ROOT_FORMAL[unit_id]
        successor = stored.get("successor")
        successor_unit_id = successor.get("unit_id") if isinstance(successor, Mapping) else None
        observed_formal = {
            "disposition": stored.get("disposition"),
            "strangle_status": stored.get("strangle_status"),
            "owner": stored.get("owner"),
            "owner_slice": stored.get("owner_slice"),
            "successor_unit_id": successor_unit_id,
            "reference_census_id": stored.get("reference_census_id"),
        }
        if observed_formal != formal:
            raise ValueError(f"DS9 C07 root formal preimage drift:{unit_id}")
        if unit_id == "cache-local-disputes" and (
            not isinstance(successor, Mapping)
            or successor.get("consumer_refs") != DS9_C07_LOCAL_DISPUTE_SUCCESSOR_REFS
        ):
            raise ValueError("DS9 C07 local-dispute successor preimage drift")
        opening_metadata = {
            "decision_date": "2026-07-17",
            "seed_rule": DS9_C07_OPENING_SEED_RULE[unit_id],
            "rationale": DS9_C07_OPENING_ROOT_RATIONALES[unit_id],
        }
        candidate_metadata = {
            "decision_date": DS9_C07_DECISION_DATE,
            "seed_rule": DS9_C07_SCOPE_SEED_RULE[scope],
            "rationale": DS9_C07_ROOT_RATIONALES[unit_id],
        }
        observed_metadata = {key: stored.get(key) for key in candidate_metadata}
        if observed_metadata not in (opening_metadata, candidate_metadata):
            raise ValueError(f"DS9 C07 root metadata preimage drift:{unit_id}")
        candidate_row = dict(stored)
        candidate_row.update(candidate_metadata)
        replacements.append((start, end, _render_root_entry(candidate_row)))

    candidate = text
    for start, end, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:start] + replacement + candidate[end:]
    return candidate


def _ds9_c07_supplemental_transition_text(
    text: str,
    *,
    scan: Mapping[str, Any] | None = None,
) -> str:
    """Refresh five adjudications and three receipts induced by DS9 source moves."""
    expected_rows = {row["finding_id"]: row for row in _supplemental_findings()}
    expected_rows.update({row["finding_id"]: row for row in _authority_presentation_rows(scan)})
    if not DS9_C07_REFRESH_FINDING_IDS.issubset(expected_rows):
        raise ValueError("DS9 C07 generated supplemental denominator drift")
    _start, _end, spans = _supplemental_section_spans(text)
    span_by_id = {
        finding_id: (object_start, object_end)
        for finding_id, object_start, object_end in spans
        if finding_id in DS9_C07_REFRESH_FINDING_IDS
    }
    if set(span_by_id) != DS9_C07_REFRESH_FINDING_IDS:
        raise ValueError("DS9 C07 supplemental target cardinality drift")
    candidate = text
    for finding_id, (start, end) in sorted(
        span_by_id.items(), key=lambda item: item[1][0], reverse=True
    ):
        replacement = _render_supplemental_finding(expected_rows[finding_id])
        candidate = candidate[:start] + replacement + candidate[end + 1 :]
    return candidate


def _ds9_c07_target_spans(
    text: str,
) -> list[tuple[str, int, int]]:
    """Locate every surgical target with exclusive end offsets."""
    spans: list[tuple[str, int, int]] = [
        (label, start, end)
        for label, start, end, _value in _ds9_c07_storage_target_spans(text)
    ]
    for unit_id in DS9_C07_ROOT_SCOPE:
        start, end, _row = _json_entry_object_span(text, unit_id)
        spans.append((f"root:{unit_id}", start, end))
    _start, _end, supplemental = _supplemental_section_spans(text)
    for finding_id, start, end in supplemental:
        if finding_id in DS9_C07_REFRESH_FINDING_IDS:
            spans.append((f"supplemental:{finding_id}", start, end + 1))
    expected_labels = {
        "induced:storage_factory_source_fingerprint",
        "induced:storage_site_source_fingerprint",
        "induced:storage_authority_factory_receipts_sha256",
        "induced:storage_rows_sha256",
        *(f"root:{unit_id}" for unit_id in DS9_C07_ROOT_SCOPE),
        *(f"supplemental:{finding_id}" for finding_id in DS9_C07_REFRESH_FINDING_IDS),
    }
    if {label for label, _start, _end in spans} != expected_labels:
        raise ValueError("DS9 C07 preservation target denominator drift")
    return sorted(spans, key=lambda item: item[1])


def _ds9_c07_preservation_errors(original_text: str, candidate_text: str) -> list[str]:
    """Prove every byte outside the adjudications and induced receipts is unchanged."""
    try:
        original_spans = _ds9_c07_target_spans(original_text)
        candidate_spans = _ds9_c07_target_spans(candidate_text)
    except (json.JSONDecodeError, ValueError) as exc:
        return [f"ds9_c07_preservation_span_invalid:{exc}"]
    original_labels = [label for label, _start, _end in original_spans]
    candidate_labels = [label for label, _start, _end in candidate_spans]
    if original_labels != candidate_labels:
        return ["ds9_c07_preservation_target_order_drift"]

    def gaps(text: str, spans: Sequence[tuple[str, int, int]]) -> list[str]:
        result: list[str] = []
        previous = 0
        for _label, start, end in spans:
            result.append(text[previous:start])
            previous = end
        result.append(text[previous:])
        return result

    if gaps(original_text, original_spans) != gaps(candidate_text, candidate_spans):
        return ["ds9_c07_non_target_byte_drift"]
    return []


def _ds9_c07_register_candidate_text(
    original_text: str,
    *,
    scan: Mapping[str, Any] | None = None,
) -> str:
    """Build and self-check the complete DS9 C07 surgical register candidate."""
    candidate = _ds9_c07_storage_transition_text(original_text)
    candidate = _ds9_c07_root_transition_text(candidate)
    candidate = _ds9_c07_supplemental_transition_text(candidate, scan=scan)
    preservation_errors = _ds9_c07_preservation_errors(original_text, candidate)
    if preservation_errors:
        raise ValueError(";".join(preservation_errors))
    repeated = _ds9_c07_storage_transition_text(candidate)
    repeated = _ds9_c07_root_transition_text(repeated)
    repeated = _ds9_c07_supplemental_transition_text(repeated, scan=scan)
    if repeated != candidate:
        raise ValueError("DS9 C07 register candidate is not idempotent")
    return candidate


def _c13_receipt_shape_errors(receipt: Mapping[str, Any]) -> list[str]:
    """Evaluate every independently observed C13 conjunct without collapsing it."""
    errors: list[str] = []
    if (
        receipt.get("receipt_id") != "ds6-c13-independent-run-paper-closure"
        or receipt.get("schema_version") != "1.0"
        or receipt.get("predicate_provenance") != "recomputed"
        or receipt.get("verified_revision") != C13_VERIFIED_REVISION
        or receipt.get("evidence_revision") != C13_EVIDENCE_REVISION
        or receipt.get("repair_commit") != C13_REPAIR_COMMIT
    ):
        errors.append("identity")
    if receipt.get("test_titles") != C13_TEST_TITLES:
        errors.append("test_title_population")
    command = receipt.get("command", {})
    if not isinstance(command, Mapping) or any(
        command.get(field) != expected
        for field, expected in {
            "global_timeout_ms": 240000,
            "grep": "DS8 governed run paper",
            "include_run_paper_fixtures": True,
            "project": "chromium",
            "reporter": "json",
            "workers": 1,
            "retries": 0,
            "timeout_ms": 90000,
            "update_snapshots": "none",
        }.items()
    ):
        errors.append("command_not_no_writer_single_worker")
    captures = receipt.get("captures")
    if not isinstance(captures, list) or len(captures) != 2:
        return [*errors, "capture_cardinality"]
    outputs = [capture.get("output") for capture in captures]
    expected_outputs = [
        "docs/plans/active/atlas-slices/receipts/ds6-c13-raw/run-1",
        "docs/plans/active/atlas-slices/receipts/ds6-c13-raw/run-2",
    ]
    if outputs != expected_outputs or [
        capture.get("capture_id") for capture in captures
    ] != ["ds6-c13-verification-1", "ds6-c13-verification-2"]:
        errors.append("capture_output_not_distinct")
    environment = receipt.get("environment")
    environment_sha256 = _canonical_sha256(environment)
    if (
        not isinstance(environment, Mapping)
        or environment.get("commit") != C13_VERIFIED_REVISION
        or receipt.get("environment_sha256_receipts")
        != [environment_sha256] * 3
    ):
        errors.append("capture_environment_drift")
    environment_producer = receipt.get("environment_probe_producer")
    if not isinstance(environment_producer, Mapping) or (
        environment_producer.get("path") != C13_ENVIRONMENT_PRODUCER_REF
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(environment_producer.get("sha256", ""))
        )
    ):
        errors.append("environment_probe_producer")
    for index, capture in enumerate(captures, 1):
        if (
            capture.get("exit_code") != 0
            or capture.get("retries") != 0
            or capture.get("environment_sha256") != environment_sha256
        ):
            errors.append(f"capture_{index}_not_zero_exit_no_retry")
        if capture.get("tests") != {
            "total": 3,
            "passed": 3,
            "failed": 0,
            "skipped": 0,
        }:
            errors.append(f"capture_{index}_test_population")
        pdfs = capture.get("pdfs")
        if not isinstance(pdfs, Mapping):
            errors.append(f"capture_{index}_pdf_missing")
            continue
        base_count = pdfs.get("base_page_count")
        grown_count = pdfs.get("grown_page_count")
        if (
            type(base_count) is not int
            or type(grown_count) is not int
            or (base_count, grown_count) != (5, 30)
        ):
            errors.append(f"capture_{index}_growth_not_admitted")
        for field in ("max_width_delta_pt", "max_height_delta_pt"):
            delta = pdfs.get(field)
            if (
                not isinstance(delta, (int, float))
                or isinstance(delta, bool)
                or delta >= 0.5
            ):
                errors.append(f"capture_{index}_{field}")
        width = pdfs.get("box_width_pt")
        height = pdfs.get("box_height_pt")
        if (
            not isinstance(width, (int, float))
            or not isinstance(height, (int, float))
            or isinstance(width, bool)
            or isinstance(height, bool)
            or width >= height
        ):
            errors.append(f"capture_{index}_not_portrait")

    snapshot = receipt.get("snapshot", {})
    if not isinstance(snapshot, Mapping) or (
        snapshot.get("sha256")
        != "26cca8a75e61cfcf8873cfc7417b6bb0c7f2cacdd8490bfa45d256422513041a"
        or snapshot.get("bytes") != 19197
        or (snapshot.get("width"), snapshot.get("height")) != (746, 84)
        or snapshot.get("sha256_receipts") != [snapshot.get("sha256")] * 3
    ):
        errors.append("snapshot_receipt_drift")
    semantics = receipt.get("semantic_conjunction", {})
    false_counts = (
        "overview_paper_payload_count",
        "visible_controls",
        "browser_local_state",
        "hud_craft_chrome",
        "signed_targets",
        "synthetic_links",
    )
    true_predicates = (
        "report_is_sole_paper_emitter",
        "visible_links_equal_admitted_packet_links",
        "machine_bytes_equal_exact_single_response_body",
        "bounded_identity_matches_after_font_readiness",
    )
    if not isinstance(semantics, Mapping) or any(
        semantics.get(field) != 0 for field in false_counts
    ) or any(semantics.get(field) is not True for field in true_predicates):
        errors.append("semantic_conjunction_false")
    bindings = receipt.get("source_bindings")
    if (
        not isinstance(bindings, list)
        or [
            row.get("path") for row in bindings if isinstance(row, Mapping)
        ]
        != C13_SOURCE_REFS
        or any(
            not isinstance(row, Mapping)
            or not isinstance(row.get("path"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256", "")))
            for row in bindings
        )
    ):
        errors.append("source_population")
    observed = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if observed != C13_RECEIPT_SHA256:
        errors.append(f"receipt_identity:{observed}")
    return errors


def _c13_independent_print_receipt(
    source_text: str | None = None,
) -> dict[str, Any]:
    """Admit exactly the independently recomputed two-run journal receipt."""
    if source_text is None:
        source_text = (
            REPO_ROOT
            / "docs/plans/active/atlas-slices/DS6-evidence-workflow-journal.md"
        ).read_text(encoding="utf-8")
    if (
        source_text.count(C13_RECEIPT_START) != 1
        or source_text.count(C13_RECEIPT_END) != 1
    ):
        raise ValueError("C13 independent receipt rejected:marker cardinality")
    payload = source_text.split(C13_RECEIPT_START, 1)[1].split(
        C13_RECEIPT_END, 1
    )[0]
    try:
        receipt = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("C13 independent receipt rejected:invalid JSON") from exc
    if not isinstance(receipt, dict):
        raise ValueError("C13 independent receipt rejected:not an object")
    shape_errors = _c13_receipt_shape_errors(receipt)
    if shape_errors:
        raise ValueError("C13 independent receipt rejected:" + ";".join(shape_errors))
    return receipt


def _c13_raw_specs(suites: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    specs: list[Mapping[str, Any]] = []
    for suite in suites:
        specs.extend(
            spec for spec in suite.get("specs", []) if isinstance(spec, Mapping)
        )
        children = suite.get("suites", [])
        if isinstance(children, list):
            specs.extend(
                _c13_raw_specs(
                    [child for child in children if isinstance(child, Mapping)]
                )
            )
    return specs


def _c13_pdf_geometry(
    pdf_bytes: bytes, geometry_bytes: bytes, *, expected_pages: int
) -> dict[str, Any]:
    """Recompute page count and A4 boxes from the retained raw PDF attachment."""
    page_count = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))
    boxes = [
        tuple(float(value) for value in match.groups())
        for match in re.finditer(
            rb"/MediaBox\s*\[\s*([-0-9.]+)\s+([-0-9.]+)\s+"
            rb"([-0-9.]+)\s+([-0-9.]+)\s*\]",
            pdf_bytes,
        )
    ]
    if page_count != expected_pages or len(boxes) != page_count:
        raise ValueError("C13 raw execution rejected:PDF page population")
    expected_width = 595.2756
    expected_height = 841.8898
    deltas: list[tuple[float, float]] = []
    for x0, y0, x1, y1 in boxes:
        width, height = x1 - x0, y1 - y0
        if width >= height:
            raise ValueError("C13 raw execution rejected:PDF not portrait")
        deltas.append((abs(width - expected_width), abs(height - expected_height)))
    try:
        geometry = json.loads(geometry_bytes)
    except json.JSONDecodeError as exc:
        raise ValueError("C13 raw execution rejected:geometry JSON") from exc
    if not isinstance(geometry, list) or len(geometry) != page_count:
        raise ValueError("C13 raw execution rejected:geometry population")
    for page_number, row in enumerate(geometry, 1):
        if not isinstance(row, Mapping) or row.get("pageNumber") != page_number:
            raise ValueError("C13 raw execution rejected:geometry page identity")
        for box_name in ("mediaBox", "cropBox"):
            box = row.get(box_name)
            if not isinstance(box, Mapping) or any(
                box.get(field) != expected
                for field, expected in {
                    "x": 0,
                    "y": 0,
                    "width": 594.95996,
                    "height": 841.91998,
                }.items()
            ):
                raise ValueError(f"C13 raw execution rejected:{box_name}")
    max_width = max(width for width, _height in deltas)
    max_height = max(height for _width, height in deltas)
    if max_width >= 0.5 or max_height >= 0.5:
        raise ValueError("C13 raw execution rejected:A4 tolerance")
    return {
        "page_count": page_count,
        "max_width_delta_pt": round(max_width, 5),
        "max_height_delta_pt": round(max_height, 5),
    }


def _c13_raw_execution_receipt(
    receipt: Mapping[str, Any],
    *,
    artifacts: Mapping[str, bytes] | None = None,
) -> dict[str, Any]:
    """Resolve the two raw Playwright results and three environment probes."""
    root = "docs/plans/active/atlas-slices/receipts/ds6-c13-raw"
    expected_paths = [
        f"{root}/run-1/results.json",
        f"{root}/run-1/.last-run.json",
        f"{root}/run-2/results.json",
        f"{root}/run-2/.last-run.json",
        f"{root}/environment-before.json",
        f"{root}/environment-between.json",
        f"{root}/environment-after.json",
    ]
    rows = receipt.get("raw_artifacts")
    if not isinstance(rows, list) or [
        row.get("path") for row in rows if isinstance(row, Mapping)
    ] != expected_paths:
        raise ValueError("C13 raw execution rejected:artifact population")
    expected_hashes = {str(row["path"]): str(row["sha256"]) for row in rows}
    expected_sizes = {str(row["path"]): row.get("bytes") for row in rows}
    if artifacts is None:
        artifacts = {path: (REPO_ROOT / path).read_bytes() for path in expected_paths}
    if set(artifacts) != set(expected_paths):
        raise ValueError("C13 raw execution rejected:artifact set")
    for path, expected_sha256 in expected_hashes.items():
        if (
            len(artifacts[path]) != expected_sizes[path]
            or hashlib.sha256(artifacts[path]).hexdigest() != expected_sha256
        ):
            raise ValueError(f"C13 raw execution rejected:artifact bytes:{path}")

    environments: list[Mapping[str, Any]] = []
    for phase in ("before", "between", "after"):
        path = f"{root}/environment-{phase}.json"
        environment = json.loads(artifacts[path])
        execution_tuple = environment.get("tuple")
        if (
            environment.get("schema_version") != "1.0"
            or environment.get("phase") != phase
            or not isinstance(execution_tuple, Mapping)
            or environment.get("tuple_sha256") != _canonical_sha256(execution_tuple)
        ):
            raise ValueError(f"C13 raw execution rejected:environment:{phase}")
        environments.append(execution_tuple)
    if environments != [receipt.get("environment")] * 3:
        raise ValueError("C13 raw execution rejected:environment drift")

    capture_receipts: list[dict[str, Any]] = []
    for index in (1, 2):
        result_path = f"{root}/run-{index}/results.json"
        last_path = f"{root}/run-{index}/.last-run.json"
        result = json.loads(artifacts[result_path])
        last_run = json.loads(artifacts[last_path])
        config = result.get("config", {})
        stats = result.get("stats", {})
        projects = config.get("projects", [])
        chromium = next(
            (
                project
                for project in projects
                if isinstance(project, Mapping) and project.get("name") == "chromium"
            ),
            {},
        )
        output_suffix = f"/{root}/run-{index}"
        if (
            result.get("errors") != []
            or last_run != {"status": "passed", "failedTests": []}
            or config.get("version") != receipt["environment"]["playwright"]
            or config.get("globalTimeout") != 240000
            or config.get("updateSnapshots") != "none"
            or config.get("workers") != 1
            or config.get("reporter") != [["json"]]
            or chromium.get("retries") != 0
            or chromium.get("timeout") != 90000
            or not str(chromium.get("outputDir", "")).endswith(output_suffix)
            or any(stats.get(field) != expected for field, expected in {
                "expected": 3,
                "skipped": 0,
                "unexpected": 0,
                "flaky": 0,
            }.items())
        ):
            raise ValueError(f"C13 raw execution rejected:run {index} metadata")
        specs = _c13_raw_specs(result.get("suites", []))
        if [spec.get("title") for spec in specs] != C13_TEST_TITLES:
            raise ValueError(f"C13 raw execution rejected:run {index} titles")
        results: dict[str, Mapping[str, Any]] = {}
        for spec in specs:
            tests = spec.get("tests", [])
            if len(tests) != 1 or tests[0].get("projectName") != "chromium":
                raise ValueError(f"C13 raw execution rejected:run {index} test")
            test_results = tests[0].get("results", [])
            if (
                tests[0].get("status") != "expected"
                or len(test_results) != 1
                or test_results[0].get("status") != "passed"
                or test_results[0].get("retry") != 0
            ):
                raise ValueError(f"C13 raw execution rejected:run {index} result")
            results[str(spec["title"])] = test_results[0]
        pdf_result = results[C13_TEST_TITLES[1]]
        attachments = {
            str(row.get("name")): row
            for row in pdf_result.get("attachments", [])
            if isinstance(row, Mapping)
        }
        expected_attachments = {
            "run-paper-empty.pdf",
            "run-paper-empty-geometry.json",
            "run-paper-growth.pdf",
            "run-paper-growth-geometry.json",
        }
        expected_content_types = {
            "run-paper-empty.pdf": "application/pdf",
            "run-paper-empty-geometry.json": "application/json",
            "run-paper-growth.pdf": "application/pdf",
            "run-paper-growth-geometry.json": "application/json",
        }
        if set(attachments) != expected_attachments or any(
            "body" not in attachment
            or attachment.get("contentType") != expected_content_types[name]
            for name, attachment in attachments.items()
        ):
            raise ValueError(f"C13 raw execution rejected:run {index} attachments")
        decoded = {
            name: base64.b64decode(str(attachment["body"]), validate=True)
            for name, attachment in attachments.items()
        }
        empty = _c13_pdf_geometry(
            decoded["run-paper-empty.pdf"],
            decoded["run-paper-empty-geometry.json"],
            expected_pages=5,
        )
        grown = _c13_pdf_geometry(
            decoded["run-paper-growth.pdf"],
            decoded["run-paper-growth-geometry.json"],
            expected_pages=30,
        )
        capture_receipts.append(
            {
                "base_page_count": empty["page_count"],
                "grown_page_count": grown["page_count"],
                "base_sha256": hashlib.sha256(
                    decoded["run-paper-empty.pdf"]
                ).hexdigest(),
                "grown_sha256": hashlib.sha256(
                    decoded["run-paper-growth.pdf"]
                ).hexdigest(),
                "max_width_delta_pt": max(
                    empty["max_width_delta_pt"], grown["max_width_delta_pt"]
                ),
                "max_height_delta_pt": max(
                    empty["max_height_delta_pt"], grown["max_height_delta_pt"]
                ),
            }
        )
    return {
        "captures": capture_receipts,
        "environment_tuple_count": len({_canonical_sha256(row) for row in environments}),
        "page_counts": [
            [row["base_page_count"], row["grown_page_count"]]
            for row in capture_receipts
        ],
        "test_titles": list(C13_TEST_TITLES),
    }


def _c13_verify_current_print_evidence(
    receipt: Mapping[str, Any],
    *,
    evidence_bytes: Mapping[str, bytes] | None = None,
) -> None:
    """Content-bind the admitted execution to the exact current property owners."""
    if _c13_receipt_shape_errors(receipt):
        raise ValueError("C13 current evidence drift:receipt")
    raw_receipt = _c13_raw_execution_receipt(receipt)
    for captured, recorded in zip(raw_receipt["captures"], receipt["captures"]):
        for field, actual in captured.items():
            if recorded["pdfs"].get(field) != actual:
                raise ValueError(f"C13 current evidence drift:raw {field}")
    for row in receipt["raw_artifacts"]:
        source_ref = str(row["path"])
        committed_bytes = _c03_git_bytes(
            "show",
            f"{C13_EVIDENCE_REVISION}:policy-engine/{source_ref}",
        )
        if hashlib.sha256(committed_bytes).hexdigest() != row["sha256"]:
            raise ValueError(f"C13 current evidence drift:raw history:{source_ref}")
    bindings = {
        str(row["path"]): str(row["sha256"])
        for row in receipt["source_bindings"]
    }
    if evidence_bytes is None:
        evidence_bytes = {
            source_ref: (REPO_ROOT / source_ref).read_bytes()
            for source_ref in bindings
        }
    if set(evidence_bytes) != set(bindings):
        raise ValueError("C13 current evidence drift:source population")
    for source_ref, expected_sha256 in bindings.items():
        observed_sha256 = hashlib.sha256(evidence_bytes[source_ref]).hexdigest()
        if observed_sha256 != expected_sha256:
            raise ValueError(f"C13 current evidence drift:{source_ref}")
        verified_bytes = _c03_git_bytes(
            "show",
            f"{C13_VERIFIED_REVISION}:policy-engine/{source_ref}",
        )
        if hashlib.sha256(verified_bytes).hexdigest() != expected_sha256:
            raise ValueError(f"C13 current evidence drift:history:{source_ref}")

    producer = receipt["environment_probe_producer"]
    producer_ref = str(producer["path"])
    producer_bytes = (REPO_ROOT / producer_ref).read_bytes()
    if hashlib.sha256(producer_bytes).hexdigest() != producer["sha256"]:
        raise ValueError("C13 current evidence drift:environment producer")
    committed_producer = _c03_git_bytes(
        "show",
        f"{C13_EVIDENCE_REVISION}:policy-engine/{producer_ref}",
    )
    if hashlib.sha256(committed_producer).hexdigest() != producer["sha256"]:
        raise ValueError("C13 current evidence drift:environment producer history")

    snapshot = receipt["snapshot"]
    snapshot_bytes = evidence_bytes[str(snapshot["path"])]
    if len(snapshot_bytes) != snapshot["bytes"]:
        raise ValueError("C13 current evidence drift:snapshot bytes")
    if snapshot_bytes[:8] != b"\x89PNG\r\n\x1a\n" or len(snapshot_bytes) < 24:
        raise ValueError("C13 current evidence drift:snapshot format")
    width = int.from_bytes(snapshot_bytes[16:20], "big")
    height = int.from_bytes(snapshot_bytes[20:24], "big")
    if (width, height) != (snapshot["width"], snapshot["height"]):
        raise ValueError("C13 current evidence drift:snapshot dimensions")
    legacy_snapshot = (
        REPO_ROOT
        / "apps/runtime-dashboard/e2e/"
        "runtime-dashboard.visual.spec.ts-snapshots/"
        "run-detail-a4-print-chromium-darwin.png"
    )
    if legacy_snapshot.exists():
        raise ValueError("C13 current evidence drift:legacy snapshot restored")

    for ancestor, descendant, label in (
        (C13_REPAIR_COMMIT, C13_VERIFIED_REVISION, "repair"),
        (C13_VERIFIED_REVISION, C13_EVIDENCE_REVISION, "evidence"),
        (C13_EVIDENCE_REVISION, "HEAD", "evidence revision"),
    ):
        ancestry = subprocess.run(  # noqa: S603 - fixed Git command
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],  # noqa: S607
            cwd=REPO_ROOT.parent,
            check=False,
        )
        if ancestry.returncode != 0:
            raise ValueError(f"C13 current evidence drift:{label} ancestry")
    snapshot_at_repair = _c03_git_bytes(
        "show",
        f"{C13_REPAIR_COMMIT}:policy-engine/{snapshot['path']}",
    )
    if hashlib.sha256(snapshot_at_repair).hexdigest() != snapshot["sha256"]:
        raise ValueError("C13 current evidence drift:first derivation bytes")
    legacy_at_repair = subprocess.run(  # noqa: S603 - fixed Git command
        [  # noqa: S607
            "git",
            "cat-file",
            "-e",
            f"{C13_REPAIR_COMMIT}:policy-engine/apps/runtime-dashboard/e2e/"
            "runtime-dashboard.visual.spec.ts-snapshots/"
            "run-detail-a4-print-chromium-darwin.png",
        ],
        cwd=REPO_ROOT.parent,
        capture_output=True,
        check=False,
    )
    if legacy_at_repair.returncode == 0:
        raise ValueError("C13 current evidence drift:legacy present at repair")


def _c13_print_open_entry() -> dict[str, Any]:
    """Return the sole admitted predecessor for the C13 transition."""
    return {
        "unit_id": C13_PRINT_ROOT_ID,
        "evidence_link": {
            "ds1_entry_id": C13_PRINT_ROOT_ID,
            "ds2_adoption_ids": [],
        },
        "disposition": "rebind_pending",
        "strangle_status": "pending",
        "owner": "team-design",
        "owner_slice": "DS8",
        "decision_date": DECISION_DATE,
        "seed_rule": "ds1_incomplete_rebind_pending",
        "rationale": C13_PRINT_OPEN_RATIONALE,
    }


def _c13_print_closed_entry(
    receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce the narrow strangled predecessor without closing the broad unit."""
    if receipt is None:
        receipt = _c13_independent_print_receipt()
    _c13_verify_current_print_evidence(receipt)
    closed = _c13_print_open_entry()
    closed["strangle_status"] = "strangled"
    closed["successor"] = {
        "unit_id": C13_PRINT_SUCCESSOR_ID,
        "consumer_refs": list(C13_PRINT_SUCCESSOR_REFS),
    }
    closed["rationale"] = C13_PRINT_RATIONALE
    return closed


def _c13_print_transition_text(
    text: str,
    *,
    receipt: Mapping[str, Any] | None = None,
) -> str:
    """Surgically strangle the exact admitted print predecessor, once."""
    if receipt is None:
        receipt = _c13_independent_print_receipt()
    start, end, stored = _json_entry_object_span(text, C13_PRINT_ROOT_ID)
    admitted_open = _c13_print_open_entry()
    admitted_closed = _c13_print_closed_entry(receipt)
    if stored == admitted_closed:
        return text
    if stored != admitted_open:
        raise ValueError(
            "C13 print transition rejected:predecessor:"
            + hashlib.sha256(
                json.dumps(stored, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )
    rendered = json.dumps(admitted_closed, indent=2, ensure_ascii=False).replace(
        "\n", "\n    "
    )
    return text[:start] + rendered + text[end:]


def _c11b_query_memory_transition_text(text: str) -> str:
    """Surgically produce C11b's exact owner-bound query-memory transition."""
    start, end, source = _json_entry_object_span(
        text, C11B_QUERY_MEMORY_ROOT_ID
    )
    successor = source.get("successor")
    if (
        source.get("strangle_status") == "strangled"
        and source.get("rationale") == C11B_QUERY_MEMORY_RATIONALE
        and isinstance(successor, Mapping)
        and successor.get("unit_id") == C11B_QUERY_MEMORY_SUCCESSOR_ID
        and successor.get("consumer_refs") == C11B_QUERY_MEMORY_SUCCESSOR_REFS
    ):
        errors: list[str] = []
        _validate_c11b_query_memory_root(
            {C11B_QUERY_MEMORY_ROOT_ID: source}, errors
        )
        if errors:
            raise ValueError(";".join(errors))
        return text

    pending_fields = {
        "disposition": "rebind_pending",
        "strangle_status": "pending",
        "owner": "team-architecture",
        "owner_slice": "DS5",
        "seed_rule": "ds1_incomplete_rebind_pending",
        "rationale": C11B_QUERY_MEMORY_PENDING_RATIONALE,
    }
    if any(source.get(field) != expected for field, expected in pending_fields.items()):
        raise ValueError("c11b_query_memory_transition_source_drift")
    if "successor" in source:
        raise ValueError("c11b_query_memory_transition_source_successor")

    transitioned: dict[str, Any] = {}
    for field, value in source.items():
        if field == "strangle_status":
            value = "strangled"
        if field == "rationale":
            transitioned["successor"] = {
                "unit_id": C11B_QUERY_MEMORY_SUCCESSOR_ID,
                "consumer_refs": C11B_QUERY_MEMORY_SUCCESSOR_REFS,
            }
            value = C11B_QUERY_MEMORY_RATIONALE
        transitioned[field] = value
    errors = []
    _validate_c11b_query_memory_root(
        {C11B_QUERY_MEMORY_ROOT_ID: transitioned}, errors
    )
    if errors:
        raise ValueError(";".join(errors))
    replacement = json.dumps(transitioned, indent=2, ensure_ascii=False).replace(
        "\n", "\n    "
    )
    return text[:start] + replacement + text[end:]


def _ds15_query_memory_transition_text(text: str) -> str:
    """Extend the strangled query root to DS15's complete live consumer set."""
    start, end, source = _json_entry_object_span(
        text, C11B_QUERY_MEMORY_ROOT_ID
    )
    successor = source.get("successor")
    final = (
        source.get("strangle_status") == "strangled"
        and source.get("rationale") == DS15_QUERY_MEMORY_RATIONALE
        and isinstance(successor, Mapping)
        and successor.get("unit_id") == C11B_QUERY_MEMORY_SUCCESSOR_ID
        and successor.get("consumer_refs") == DS15_QUERY_MEMORY_SUCCESSOR_REFS
    )
    if final:
        errors: list[str] = []
        _validate_c11b_query_memory_root(
            {C11B_QUERY_MEMORY_ROOT_ID: source}, errors
        )
        if errors:
            raise ValueError(";".join(errors))
        return text

    opening_fields = {
        "disposition": "rebind_pending",
        "strangle_status": "strangled",
        "owner": "team-architecture",
        "owner_slice": "DS5",
        "seed_rule": "ds1_incomplete_rebind_pending",
        "rationale": C11B_QUERY_MEMORY_OPENING_RATIONALE,
    }
    if any(source.get(field) != expected for field, expected in opening_fields.items()):
        raise ValueError("ds15_query_memory_transition_source_drift")
    if not isinstance(successor, Mapping):
        raise ValueError("ds15_query_memory_transition_source_successor")
    if (
        successor.get("unit_id") != C11B_QUERY_MEMORY_SUCCESSOR_ID
        or successor.get("consumer_refs")
        != C11B_QUERY_MEMORY_OPENING_SUCCESSOR_REFS
    ):
        raise ValueError("ds15_query_memory_transition_source_successor_drift")

    transitioned = copy.deepcopy(dict(source))
    transitioned["successor"] = {
        "unit_id": C11B_QUERY_MEMORY_SUCCESSOR_ID,
        "consumer_refs": DS15_QUERY_MEMORY_SUCCESSOR_REFS,
    }
    transitioned["rationale"] = DS15_QUERY_MEMORY_RATIONALE
    errors = []
    _validate_c11b_query_memory_root(
        {C11B_QUERY_MEMORY_ROOT_ID: transitioned}, errors
    )
    if errors:
        raise ValueError(";".join(errors))
    return text[:start] + _render_root_entry(transitioned) + text[end:]

C23_ROOT_IDS = frozenset(
    {
        "status-stress-scene",
        "status-inline-readiness-evidence",
        "status-inline-readiness-gate",
        "status-inline-readiness-review",
    }
)
C23_SUCCESSOR_ID = "c23-readiness-scientific-containment"
C23_SUCCESSOR_REFS = [
    "apps/runtime-dashboard/src/features/runs/components/PublicSectorReadinessPanel.tsx",
    "apps/runtime-dashboard/src/features/runs/components/ScientificDepthPanel.tsx",
    "apps/runtime-dashboard/src/features/runs/components/ds16SuccessorContainment.test.ts",
]
C23_RATIONALE = (
    "C23 deleted dashboard-local readiness and scientific synthesis; DS16 commit "
    "fa325dcfe83439fc624fcc09865c823e6b128ae3 replaced "
    "readinessScientificContainment.test.ts with ds16SuccessorContainment.test.ts, bound "
    "the retained panels to runtime-served typed refusals, and retained the exact "
    "no-local-authority gate."
)

C17B_SCOPED_ENVELOPE_OWNER = (
    "apps/runtime-dashboard/src/app/offline/authorityLocalState.ts"
)
C17B_REGISTERED_CODEC_BY_OWNER = {
    C17B_SCOPED_ENVELOPE_OWNER: "authority-local-state-envelope-v1",
    "apps/runtime-dashboard/src/features/composer/state/composerDraftRepository.ts": (
        "composer-draft-v1"
    ),
    "apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts": (
        "clerk-chat-sessions-v1"
    ),
    "apps/runtime-dashboard/src/features/runs/domain/disputes.ts": (
        "dispute-topology-v1"
    ),
    "apps/runtime-dashboard/src/features/runs/domain/operatorCraft.ts": (
        "operator-craft-family-codecs-v1"
    ),
    "apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx": (
        "causal-draft-v1"
    ),
}
C17B_BENIGN_REASON_BY_OWNER = {
    "apps/runtime-dashboard/src/app/providers/InterfaceModeProvider.tsx": "ui_preference",
    "apps/runtime-dashboard/src/app/providers/ThemeProvider.tsx": "theme",
    "apps/runtime-dashboard/src/app/providers/TrustViewProvider.tsx": "ui_preference",
    "apps/runtime-dashboard/src/app/state/usePreferencesStore.ts": "ui_preference",
    "apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts": "ui_preference",
    "apps/runtime-dashboard/src/features/dashboard/state/useDashboardLayoutStore.ts": (
        "ui_preference"
    ),
    "apps/runtime-dashboard/src/shared/i18n/locale.ts": "locale",
    "apps/runtime-dashboard/src/shared/lib/featureFlags.ts": (
        "rollout_exposure_control"
    ),
}
C17B_STORAGE_CLASS_COUNTS = {
    "interaction_benign": 22,
    "rollout_cache_pending": 0,
    "scoped_authority": 14,
}
C17B_AUTHORITY_FLOW_LIMITATION = {
    "direct_construction_provenance": "recomputed",
    "semantic_class_provenance": "institutionally_supplied",
    "authority_flow_provenance": "not_established",
    "authority_flow_scope": (
        "site-to-owner-instance provider, receiver, key, and payload value flow is "
        "outside the declaration-resolved direct-construction census"
    ),
    "authority_flow_falsifier": (
        "const storage = provider(); storage.setItem(...) preserves a resolved "
        "Storage.setItem site while changing the unproved owner-instance flow"
    ),
    "authority_flow_required_capability": (
        "sound whole-program interprocedural data/control-flow with reaching "
        "definitions and owner-instance identity"
    ),
    "authority_flow_capability_status": "absent/unallocated",
}

EXPECTED_FINDING_IDS = (
    BASE_EXPECTED_FINDING_IDS
    | set(GOVERNED_DEBT_DESCRIPTORS)
    | set(AUTHORITY_PRESENTATION_DEBT_SPECS)
    | set(DS11_TRUST_PRESENTATION_FINDING_IDS)
)

REPORT_PROJECTION_START = "<!-- BEGIN DS19 REGISTER PROJECTION -->"
REPORT_PROJECTION_END = "<!-- END DS19 REGISTER PROJECTION -->"

DS8_STRANGLE_BASE_COMMIT = "9e6a43b53d11166e90df376940cb34ff15b77289"
DS8_STRANGLE_SOURCE_COMMIT = "fd43342f87fda34c6123a8f5f4791f8e3236b4f9"
DS8_STRANGLE_WRITER_HEAD_COMMIT = "c393090ab35c242b03314cd2095d195c4e188fc3"
DS8B_TRANSITION_BASE_COMMIT = "23a2c797bececb1757253aa4f1e8ef5999c81601"
DS8B_TRANSITION_SOURCE_COMMIT = "40226aafe0f668d87aa52fda696cc72fec0be0b5"
DS8_STRANGLE_ROOTS = (
    "apps/runtime-dashboard/src/features/runs",
    "apps/runtime-dashboard/src/features/artifacts",
    "apps/runtime-dashboard/src/features/evidence",
)
DS8_STRANGLE_EXTENSIONS = (".ts", ".tsx")
DS8_BASELINE_CONTENT_REANCHORS = frozenset(
    {
        (
            "C06",
            "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx",
        ),
        (
            "C08",
            "apps/runtime-dashboard/src/features/evidence/components/"
            "DataIntelligencePanel.test.tsx",
        ),
        (
            "C08",
            "apps/runtime-dashboard/src/features/evidence/components/"
            "DataIntelligencePanel.tsx",
        ),
    }
)
DS10_BASELINE_CONTENT_REANCHORS = frozenset(
    {
        (
            "C06",
            "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts",
        ),
        (
            "C06",
            "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx",
        ),
        (
            "C08",
            "apps/runtime-dashboard/src/features/evidence/components/"
            "DataIntelligencePanel.test.tsx",
        ),
        (
            "C08",
            "apps/runtime-dashboard/src/features/evidence/components/"
            "DataIntelligencePanel.tsx",
        ),
    }
)
DS8_COMPANION_REFERENCE_PATHS = {
    "c06-cgf-public-vocabulary-producer-debt": (
        "architecture/atlas_surfaces/ds4-waist-debt-register.json"
    ),
    "c06-decision-grade-generated-contract-debt": (
        "architecture/atlas_surfaces/ds4-waist-debt-register.json"
    ),
    "c08b-auth-session-revision-producer-debt": (
        "apps/runtime-dashboard/src/api/queryKeys.ts"
    ),
}
DS8_STRANGLE_IN_SCOPE = frozenset(
    {
        "apps/runtime-dashboard/src/features/runs/route.tsx",
        "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx",
        "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx",
        "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx",
        "apps/runtime-dashboard/src/features/artifacts/components/ArtifactViewerRegistry.tsx",
        "apps/runtime-dashboard/src/features/artifacts/components/DecisionCardView.tsx",
        "apps/runtime-dashboard/src/features/evidence/components/FreshnessBraidPanel.tsx",
        "apps/runtime-dashboard/src/features/evidence/components/DataIntelligencePanel.tsx",
    }
)
DS8_STRANGLE_CLOSURE_PATHS = {
    "C04": (
        "apps/runtime-dashboard/src/features/artifacts/components/ArtifactViewerRegistry.tsx",
        "apps/runtime-dashboard/src/features/artifacts/components/DecisionCardView.tsx",
        "apps/runtime-dashboard/src/features/evidence/components/FreshnessBraidPanel.tsx",
        "apps/runtime-dashboard/src/features/evidence/components/DataIntelligencePanel.tsx",
    ),
    "C05": (
        "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx",
    ),
    "C06": (
        "apps/runtime-dashboard/src/features/runs/route.tsx",
        "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx",
        "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx",
        "apps/runtime-dashboard/src/features/runs/api/useRunPaper.ts",
        "apps/runtime-dashboard/src/features/runs/components/runPaperExport.ts",
        "apps/runtime-dashboard/src/features/runs/domain/runPaperPresentation.ts",
    ),
}
DS8_DEFERRED_EXIT_CONDITION = "approved_named_successor_slice_moves_row"

# DS10 owns these ten existing DS1 roots. Fixed chrome remains local; only the
# five explicitly rebound roots carry successor receipts.
DS10_CAPABILITY_DISCOVERY_ROOTS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "route-knowledge": (
        "rebind_pending",
        "strangled",
        (
            "apps/runtime-dashboard/src/app/routes/routeManifest.ts",
            "apps/runtime-dashboard/src/features/lex/routes/LexKnowledgeGraphPage.tsx",
            "apps/runtime-dashboard/src/features/evidence/components/CapabilityDiscoveryPanel.tsx",
        ),
    ),
    "feature-command-palette": (
        "rebind_pending",
        "strangled",
        (
            "apps/runtime-dashboard/src/features/commandPalette/CommandPalette.tsx",
            "apps/runtime-dashboard/src/app/surfaces/surfaceRegistry.ts",
            "apps/runtime-dashboard/src/features/evidence/components/CapabilityDiscoveryPanel.tsx",
        ),
    ),
    "feature-lex": (
        "rebind_pending",
        "strangled",
        (
            "apps/runtime-dashboard/src/features/lex/routes/LexKnowledgeGraphPage.tsx",
            "apps/runtime-dashboard/src/features/evidence/export/capabilityDiscoveryTwin.ts",
        ),
    ),
    "api-op-get-control-capabilities": (
        "rebind_pending",
        "strangled",
        (
            "apps/runtime-dashboard/src/api/hooks/useCapabilities.ts",
            "apps/runtime-dashboard/src/shared/lib/capabilities.ts",
            "apps/runtime-dashboard/src/app/workspaces.ts",
        ),
    ),
    "api-op-search-data-catalog": (
        "rebind_pending",
        "strangled",
        (
            "apps/runtime-dashboard/src/api/hooks/useCapabilitySearch.ts",
            "apps/runtime-dashboard/src/features/evidence/components/CapabilityDiscoveryPanel.tsx",
        ),
    ),
    "api-op-get-data-index-stats": ("use_as_is", "not_applicable", ()),
    "api-op-get-lex-graph-stats": ("use_as_is", "not_applicable", ()),
    "api-op-search-lex-graph": ("use_as_is", "not_applicable", ()),
    "api-op-get-lex-pipeline-status": ("use_as_is", "not_applicable", ()),
    "api-op-trigger-lex-pipeline": ("use_as_is", "not_applicable", ()),
}

DS10_CAPABILITY_DISCOVERY_METADATA = {
    "decision_date": "2026-08-26",
    "seed_rule": "ds10_capability_discovery_adjudication",
    "rationale": (
        "DS10 separates fixed chrome and execution policy from generic "
        "capability discovery without inferring authority or admission."
    ),
}
DS10_RETIRED_CAPABILITY_DISCOVERY_SUCCESSORS = {
    "api-op-search-data-catalog": {
        "unit_id": "feature-capability-discovery",
        "consumer_refs": [
            "apps/runtime-dashboard/src/api/hooks/useDataCatalogSearch.ts",
            "apps/runtime-dashboard/src/features/evidence/components/"
            "DataIntelligencePanel.tsx",
        ],
    }
}
DS10_DECLARED_EXTERNAL_REGISTER_NONCLOSURES = (
    "c13_print_receipt_invalid:C13 current evidence drift:"
    "apps/runtime-dashboard/src/features/runs/components/AmbientTelemetryHud.tsx",
)
DS10_C13_EXTERNAL_SOURCE_BINDING_MISMATCHES = {
    (
        "apps/runtime-dashboard/src/features/runs/components/"
        "AmbientTelemetryHud.tsx"
    ): (
        "232392b06df5bbaca4380a20fd669554d9ddd0f132396c8f290dea5804faf740",
        "a06e6a98fc766b48b569d7215ee3e6f390abe8a3022ffe2bb98116ace23093cd",
    ),
    (
        "apps/runtime-dashboard/src/features/runs/components/"
        "OperatorCraftPanel.tsx"
    ): (
        "687a831dce4165393622ed37d60e4269f61b3dd424589b62fb3ae924b1196b66",
        "8d94ade694f63613d913042cf36f612e62327b843e01781cd3b9872d365702ef",
    ),
    "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx": (
        "514ddff6df513859ec99e2b429e50b7e6bf5c6417b320f416c2a576a744777df",
        "f4533fee648a8e2de5fb7ca6bedc56ac1e908b02351019950bae11b21cf25d66",
    ),
    "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx": (
        "4bb0bea6d71ad045d3d129dc9455cb0f4786d723199d77d95a372de2c22542bb",
        "5f51a10ea5f5142ce8e0000d055c2bf96ff36f7d5dd3c5c3d1ee25740aaa0f76",
    ),
    (
        "apps/runtime-dashboard/src/features/runs/routes/"
        "RunReportPage.test.tsx"
    ): (
        "d3b5819eb8e3a0390d4c7bc4f261457ddf2583d504424feaad2584c04ad5b6dd",
        "30023d274e3a48235cc72a1dbbe1ee39d8276a5299b9c2c8ab12cbd46c96d1a9",
    ),
    "apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts": (
        "c472f411f4ee512a9e1a54057b8c5a3a64130d6df8a6d79a6c09a4e5efeca8d9",
        "3a69dd559452400e50eec543fdf365c03cf5b3d358b6fc04adcb1b8953ce9ab8",
    ),
}
DS15_C13_EXTERNAL_SOURCE_BINDING_MISMATCHES = {
    **DS10_C13_EXTERNAL_SOURCE_BINDING_MISMATCHES,
    "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.test.tsx": (
        "d3b5819eb8e3a0390d4c7bc4f261457ddf2583d504424feaad2584c04ad5b6dd",
        "53e8f6a47eceec9ce35b11fe1b8af9feac454167638bec5285cf4b2443861704",
    ),
    "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx": (
        "4bb0bea6d71ad045d3d129dc9455cb0f4786d723199d77d95a372de2c22542bb",
        "65737022fc6b4c4a1c58a6aee45627be34b51a962bb0af6d145490a4496227c7",
    ),
}


def _validate_ds10_capability_discovery_roots(
    entries: Mapping[str, Mapping[str, Any]], errors: list[str]
) -> None:
    """Reject drift in the exact ten-root DS10 disposition decision."""
    ds10_entries = {
        unit_id: entry
        for unit_id, entry in entries.items()
        if entry.get("owner_slice") == "DS10"
    }
    if set(ds10_entries) != set(DS10_CAPABILITY_DISCOVERY_ROOTS):
        errors.append("ds10_capability_discovery_root_denominator_drift")
    for unit_id, (disposition, strangle_status, consumer_refs) in (
        DS10_CAPABILITY_DISCOVERY_ROOTS.items()
    ):
        entry = entries.get(unit_id)
        if not isinstance(entry, Mapping):
            errors.append(f"ds10_capability_discovery_root_missing:{unit_id}")
            continue
        if entry.get("owner") != "team-design" or entry.get("owner_slice") != "DS10":
            errors.append(f"ds10_capability_discovery_owner_drift:{unit_id}")
        if (entry.get("disposition"), entry.get("strangle_status")) != (
            disposition,
            strangle_status,
        ):
            errors.append(f"ds10_capability_discovery_transition_drift:{unit_id}")
        if any(
            entry.get(field) != expected
            for field, expected in DS10_CAPABILITY_DISCOVERY_METADATA.items()
        ):
            errors.append(f"ds10_capability_discovery_governance_drift:{unit_id}")
        successor = entry.get("successor")
        if consumer_refs:
            expected_successor = {
                "unit_id": "feature-capability-discovery",
                "consumer_refs": list(consumer_refs),
            }
            if successor != expected_successor:
                errors.append(f"ds10_capability_discovery_successor_drift:{unit_id}")
        elif successor is not None:
            errors.append(f"ds10_capability_discovery_unexpected_successor:{unit_id}")


def _ds10_capability_discovery_candidate_text(
    original_text: str, *, verify_idempotency: bool = True
) -> str:
    """Adjudicate exactly ten DS10 roots while preserving every peer byte."""
    original_data = json.loads(original_text)
    ds8_coverage = original_data.get("ds8_strangle_coverage")
    if not isinstance(ds8_coverage, Mapping):
        raise ValueError("DS10 writer requires the DS8 coverage object")
    ds8_errors = validate_ds8_strangle_coverage(ds8_coverage)
    if ds8_errors:
        raise ValueError("DS10 writer rejected DS8 drift: " + ";".join(ds8_errors))

    replacements: list[tuple[int, int, str]] = []
    opening_metadata = {
        "decision_date": "2026-07-17",
        "seed_rule": "ds1_incomplete_rebind_pending",
        "rationale": (
            "DS1 does not record this narrow unit as implemented; its owning slice "
            "must rebind or retire it without creating a parallel owner."
        ),
    }
    candidate_metadata = DS10_CAPABILITY_DISCOVERY_METADATA
    for unit_id, (disposition, strangle_status, consumer_refs) in (
        DS10_CAPABILITY_DISCOVERY_ROOTS.items()
    ):
        start, end, stored = _json_entry_object_span(original_text, unit_id)
        if (
            stored.get("owner") != "team-design"
            or stored.get("owner_slice") != "DS10"
        ):
            raise ValueError(f"DS10 root owner preimage drift:{unit_id}")
        target_successor = (
            {
                "unit_id": "feature-capability-discovery",
                "consumer_refs": list(consumer_refs),
            }
            if consumer_refs
            else None
        )
        opening = (
            stored.get("disposition") == "rebind_pending"
            and stored.get("strangle_status") == "pending"
            and stored.get("successor") is None
            and all(stored.get(key) == value for key, value in opening_metadata.items())
        )
        admitted_successors = [target_successor]
        retired_successor = DS10_RETIRED_CAPABILITY_DISCOVERY_SUCCESSORS.get(
            unit_id
        )
        if retired_successor is not None:
            admitted_successors.append(retired_successor)
        admitted = (
            stored.get("disposition") == disposition
            and stored.get("strangle_status") == strangle_status
            and stored.get("successor") in admitted_successors
            and all(
                stored.get(key) == value
                for key, value in candidate_metadata.items()
            )
        )
        if not opening and not admitted:
            raise ValueError(f"DS10 root preimage drift:{unit_id}")
        candidate_row = dict(stored)
        candidate_row.update(candidate_metadata)
        candidate_row["disposition"] = disposition
        candidate_row["strangle_status"] = strangle_status
        if target_successor is None:
            candidate_row.pop("successor", None)
        else:
            candidate_row["successor"] = target_successor
        replacements.append((start, end, _render_root_entry(candidate_row)))

    candidate = original_text
    for start, end, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:start] + replacement + candidate[end:]

    original_spans = [
        (unit_id, *_json_entry_object_span(original_text, unit_id)[:2])
        for unit_id in DS10_CAPABILITY_DISCOVERY_ROOTS
    ]
    candidate_spans = [
        (unit_id, *_json_entry_object_span(candidate, unit_id)[:2])
        for unit_id in DS10_CAPABILITY_DISCOVERY_ROOTS
    ]

    def gaps(text: str, spans: Sequence[tuple[str, int, int]]) -> list[str]:
        result: list[str] = []
        previous = 0
        for _unit_id, start, end in sorted(spans, key=lambda row: row[1]):
            result.append(text[previous:start])
            previous = end
        result.append(text[previous:])
        return result

    if gaps(original_text, original_spans) != gaps(candidate, candidate_spans):
        raise ValueError("DS10 writer changed bytes outside its ten roots")
    candidate_data = json.loads(candidate)
    errors: list[str] = []
    _validate_ds10_capability_discovery_roots(
        {row["unit_id"]: row for row in candidate_data["entries"]}, errors
    )
    if errors:
        raise ValueError("DS10 writer candidate rejected: " + ";".join(errors))
    if verify_idempotency:
        repeated = _ds10_capability_discovery_candidate_text(
            candidate, verify_idempotency=False
        )
        if repeated != candidate:
            raise ValueError("DS10 writer candidate is not idempotent")
    return candidate


def _ds10_protected_signing_census_candidate_text(original_text: str) -> str:
    """Surgically admit the complete live browser-signing identity set."""
    marker = '  "reference_censuses": ['
    if original_text.count(marker) != 1:
        raise ValueError("DS10 reference-census container drift")
    array_start = original_text.index(marker) + len(marker) - 1
    array_end = _json_container_end(original_text, array_start)
    start, end, stored = _json_object_span_by_identity(
        original_text,
        field="census_id",
        value="census-browser-signing-protected-live",
        within=(array_start, array_end + 1),
    )
    probes = stored.get("probes")
    if not isinstance(probes, list) or len(probes) != 1:
        raise ValueError("DS10 protected-signing probe cardinality drift")
    probe = probes[0]
    if not isinstance(probe, Mapping) or probe.get("kind") != "reference_count":
        raise ValueError("DS10 protected-signing probe kind drift")
    observed = _recompute_probe(probe)
    anchors = [_c21b_identity_anchor(reference) for reference in observed]
    if any(anchor is None for anchor in anchors):
        raise ValueError("DS10 protected-signing observation is unmappable")
    identities = _typescript_reference_identities_from_anchors(
        [anchor for anchor in anchors if anchor is not None]
    )
    encoded = sorted(identity["encoded_identity"] for identity in identities)
    matches, diagnostic = _probe_observation_matches_stored_mode(encoded, observed)
    if matches is not True or diagnostic is not None:
        raise ValueError(
            "DS10 protected-signing identity reconciliation failed:"
            + str(diagnostic)
        )

    refreshed = copy.deepcopy(dict(stored))
    refreshed_probe = refreshed["probes"][0]
    refreshed_probe["expected_count"] = len(encoded)
    refreshed_probe["observed_refs"] = encoded
    replacement = _render_root_entry(refreshed)
    candidate = original_text[:start] + replacement + original_text[end:]
    _repeated_start, repeated_end, repeated = _json_object_span_by_identity(
        candidate,
        field="census_id",
        value="census-browser-signing-protected-live",
        within=(array_start, _json_container_end(candidate, array_start) + 1),
    )
    if repeated != refreshed or candidate[:start] != original_text[:start]:
        raise ValueError("DS10 protected-signing census replacement drift")
    if candidate[repeated_end:] != original_text[end:]:
        raise ValueError("DS10 protected-signing census changed peer bytes")
    return candidate


def _ds10_c13_external_nonclosure_admission(
    errors: Sequence[str],
    *,
    source_bytes: Mapping[str, bytes] | None = None,
    expected_mismatches: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[tuple[str, ...], list[str]]:
    """Admit the exact fail-fast C13 error only after a complete binding census."""
    if expected_mismatches is None:
        expected_mismatches = DS10_C13_EXTERNAL_SOURCE_BINDING_MISMATCHES
    declared = DS10_DECLARED_EXTERNAL_REGISTER_NONCLOSURES[0]
    cardinality = errors.count(declared)
    if cardinality > 1:
        return (), ["ds10_c13_external_error_cardinality_drift"]

    receipt = _c13_independent_print_receipt()
    bindings = {
        str(row["path"]): str(row["sha256"])
        for row in receipt["source_bindings"]
    }
    if source_bytes is None:
        source_bytes = {
            source_ref: (REPO_ROOT / source_ref).read_bytes()
            for source_ref in bindings
        }
    if set(source_bytes) != set(bindings):
        return (), ["ds10_c13_external_source_binding_census_drift"]
    if cardinality == 0:
        try:
            _c13_verify_current_print_evidence(receipt, evidence_bytes=source_bytes)
        except ValueError:
            return (), ["ds10_c13_unexposed_current_evidence_drift"]
        return (), []

    observed_mismatches = {
        source_ref: (
            expected_sha256,
            hashlib.sha256(source_bytes[source_ref]).hexdigest(),
        )
        for source_ref, expected_sha256 in bindings.items()
        if hashlib.sha256(source_bytes[source_ref]).hexdigest() != expected_sha256
    }
    if observed_mismatches != expected_mismatches:
        return (), ["ds10_c13_external_source_binding_census_drift"]

    replay_bytes = dict(source_bytes)
    for source_ref in observed_mismatches:
        replay_bytes[source_ref] = _c03_git_bytes(
            "show",
            f"{C13_VERIFIED_REVISION}:policy-engine/{source_ref}",
        )
    try:
        _c13_verify_current_print_evidence(receipt, evidence_bytes=replay_bytes)
    except ValueError:
        return (), ["ds10_c13_external_receipt_replay_drift"]
    return DS10_DECLARED_EXTERNAL_REGISTER_NONCLOSURES, []


def _ds10_blocking_register_errors(
    errors: Sequence[str],
    *,
    admitted_external_errors: Sequence[str] = (),
) -> list[str]:
    """Return all errors except one independently admitted external residual."""
    remaining = list(errors)
    for admitted in admitted_external_errors:
        if admitted not in DS10_DECLARED_EXTERNAL_REGISTER_NONCLOSURES:
            raise ValueError(f"DS10 undeclared external register error:{admitted}")
        if remaining.count(admitted) == 1:
            remaining.remove(admitted)
    return remaining


def _write_ds10_capability_discovery_family() -> dict[str, Any]:
    """Atomically write DS10 roots and their exact governed companions."""
    original_register = REGISTER_PATH.read_text(encoding="utf-8")
    original_report = REPORT_PATH.read_text(encoding="utf-8")
    original_baseline = BASELINE_PATH.read_text(encoding="utf-8")
    baseline_candidate = _ds10_baseline_manifest_candidate_text(original_baseline)
    baseline_data = json.loads(baseline_candidate)
    refreshed_register = _ds10_protected_signing_census_candidate_text(
        original_register
    )
    refreshed_register = _refresh_supplemental_findings_text(refreshed_register)
    register_candidate = _ds10_capability_discovery_candidate_text(refreshed_register)
    data = json.loads(register_candidate)
    register_errors = validate_register(
        data,
        report_parity=False,
        baseline_manifest=baseline_data,
    )
    admitted_external_errors, external_admission_errors = (
        _ds10_c13_external_nonclosure_admission(register_errors)
    )
    pre_errors = [
        *external_admission_errors,
        *_ds10_blocking_register_errors(
            register_errors,
            admitted_external_errors=admitted_external_errors,
        ),
    ]
    pre_errors.extend(
        "baseline_" + error
        for error in validate_baseline_manifest(
            baseline_data,
            verify_source_bytes=True,
        )
    )
    if pre_errors:
        raise ValueError("DS10 family candidate rejected: " + ";".join(pre_errors))
    report_candidate = render_report(data)
    candidates = {
        REGISTER_PATH: register_candidate,
        REPORT_PATH: report_candidate,
        BASELINE_PATH: baseline_candidate,
    }

    def validate_after() -> list[str]:
        errors: list[str] = []
        if REGISTER_PATH.read_text(encoding="utf-8") != register_candidate:
            errors.append("ds10_register_readback_drift")
        if REPORT_PATH.read_text(encoding="utf-8") != report_candidate:
            errors.append("ds10_report_readback_drift")
        if BASELINE_PATH.read_text(encoding="utf-8") != baseline_candidate:
            errors.append("ds10_baseline_readback_drift")
        stored = _load_json(REGISTER_PATH)
        stored_baseline = _load_json(BASELINE_PATH)
        _validate_ds10_capability_discovery_roots(
            {row["unit_id"]: row for row in stored["entries"]}, errors
        )
        errors.extend(
            validate_ds8_strangle_coverage(stored["ds8_strangle_coverage"])
        )
        stored_register_errors = validate_register(
            stored, baseline_manifest=stored_baseline
        )
        stored_admitted, stored_admission_errors = (
            _ds10_c13_external_nonclosure_admission(stored_register_errors)
        )
        errors.extend(stored_admission_errors)
        errors.extend(
            _ds10_blocking_register_errors(
                stored_register_errors,
                admitted_external_errors=stored_admitted,
            )
        )
        errors.extend(
            "baseline_" + error
            for error in validate_baseline_manifest(
                stored_baseline,
                verify_source_bytes=True,
            )
        )
        return errors

    def pre_promote() -> None:
        if REGISTER_PATH.read_text(encoding="utf-8") != original_register:
            raise ValueError("DS10 register preimage moved before promotion")
        if REPORT_PATH.read_text(encoding="utf-8") != original_report:
            raise ValueError("DS10 report preimage moved before promotion")
        if BASELINE_PATH.read_text(encoding="utf-8") != original_baseline:
            raise ValueError("DS10 baseline preimage moved before promotion")

    _failure_atomic_write_texts(
        candidates,
        validate_after=validate_after,
        pre_promote=pre_promote,
    )
    return {
        "roots": len(DS10_CAPABILITY_DISCOVERY_ROOTS),
        "ds8_assignments": len(data["ds8_strangle_coverage"]["assignments"]),
        "baseline_reanchors": len(DS10_BASELINE_CONTENT_REANCHORS),
        "declared_external_nonclosures": list(admitted_external_errors),
        "c13_external_source_binding_mismatches": len(
            DS10_C13_EXTERNAL_SOURCE_BINDING_MISMATCHES
        ),
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _ds8_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _ds8_json_digest(value: object) -> str:
    return _ds8_digest(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def _ds8_git_bytes(*arguments: str) -> bytes:
    completed = subprocess.run(  # noqa: S603 - fixed repository command
        ["git", *arguments],  # noqa: S607 - controlled toolchain executable
        cwd=REPO_ROOT.parent,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            "DS8 Git census failed: "
            + completed.stderr.decode("utf-8", errors="replace").strip()
        )
    return completed.stdout


def _ds8_git_text(*arguments: str) -> str:
    return _ds8_git_bytes(*arguments).decode("utf-8")


@lru_cache(maxsize=1)
def _ds8_coordinate_prefix() -> str:
    completed = subprocess.run(  # noqa: S603 - fixed repository command
        ["git", "rev-parse", "--show-prefix"],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(
            "DS8 Git prefix query failed: " + completed.stderr.strip()
        )
    prefix = completed.stdout.strip()
    if prefix != "policy-engine/":
        raise ValueError(f"DS8 Git coordinate prefix drift: {prefix!r}")
    return prefix


def _ds8_role(path: str) -> str:
    if re.search(r"\.stories\.(?:ts|tsx)$", path):
        return "story"
    if re.search(r"\.(?:test|spec)\.(?:ts|tsx)$", path):
        return "test"
    return "production"


def _ds8_feature(path: str) -> str:
    for feature in ("runs", "artifacts", "evidence"):
        marker = f"/features/{feature}/"
        if marker in path:
            return feature
    raise ValueError(f"DS8 path escaped feature denominator: {path}")


def _ds8_is_source(path: str) -> bool:
    return path.endswith(DS8_STRANGLE_EXTENSIONS) and any(
        path == root or path.startswith(root + "/")
        for root in DS8_STRANGLE_ROOTS
    )


@lru_cache(maxsize=4)
def _ds8_git_tree_sources(commit: str) -> dict[str, bytes]:
    resolved = _ds8_git_text("rev-parse", f"{commit}^{{commit}}").strip()
    if resolved != commit:
        raise ValueError(f"DS8 commit is not a full immutable identity: {commit}")
    prefix = _ds8_coordinate_prefix()
    top_roots = [prefix + root for root in DS8_STRANGLE_ROOTS]
    path_output = _ds8_git_bytes(
        "ls-tree",
        "-r",
        "-z",
        "--name-only",
        commit,
        "--",
        *top_roots,
    )
    top_paths = [
        raw.decode("utf-8")
        for raw in path_output.split(b"\0")
        if raw
    ]
    paths = sorted(
        top_path[len(prefix) :]
        for top_path in top_paths
        if top_path.startswith(prefix)
        and _ds8_is_source(top_path[len(prefix) :])
    )
    return {
        path: _ds8_git_bytes("show", f"{commit}:{prefix}{path}")
        for path in paths
    }


@lru_cache(maxsize=4)
def _ds8_archive_sources(commit: str) -> dict[str, bytes]:
    prefix = _ds8_coordinate_prefix()
    archive = _ds8_git_bytes(
        "archive",
        "--format=tar",
        commit,
        "--",
        *(prefix + root for root in DS8_STRANGLE_ROOTS),
    )
    sources: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        for member in bundle.getmembers():
            if not member.isfile() or not member.name.startswith(prefix):
                continue
            path = member.name[len(prefix) :]
            if not _ds8_is_source(path):
                continue
            extracted = bundle.extractfile(member)
            if extracted is None:
                raise ValueError(f"DS8 archive member unreadable: {member.name}")
            sources[path] = extracted.read()
    return dict(sorted(sources.items()))


def _ds8_live_sources() -> dict[str, bytes]:
    physical = {
        path.relative_to(REPO_ROOT).as_posix(): path.read_bytes()
        for root in DS8_STRANGLE_ROOTS
        for path in (REPO_ROOT / root).rglob("*")
        if path.is_file()
        and path.suffix in DS8_STRANGLE_EXTENSIONS
    }
    tracked_output = subprocess.run(  # noqa: S603 - fixed repository command
        [  # noqa: S607 - controlled toolchain executable
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            *DS8_STRANGLE_ROOTS,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if tracked_output.returncode != 0:
        raise ValueError(
            "DS8 live source census failed: "
            + tracked_output.stderr.decode("utf-8", errors="replace").strip()
        )
    tracked = {
        raw.decode("utf-8")
        for raw in tracked_output.stdout.split(b"\0")
        if raw and _ds8_is_source(raw.decode("utf-8"))
    }
    if set(physical) != tracked:
        raise ValueError(
            "DS8 physical/Git live path drift: "
            f"physical_only={sorted(set(physical) - tracked)}:"
            f"git_only={sorted(tracked - set(physical))}"
        )
    return dict(sorted(physical.items()))


def _ds8_path_manifest(paths: Iterable[str], *, prefix: str) -> str:
    payload = "".join(f"{prefix}{path}\n" for path in sorted(paths)).encode()
    return _ds8_digest(payload)


def _ds8_content_manifest(
    sources: Mapping[str, bytes], paths: Iterable[str]
) -> str:
    payload = b"".join(
        path.encode()
        + b"\0"
        + hashlib.sha256(sources[path]).hexdigest().encode()
        + b"\n"
        for path in sorted(paths)
    )
    return _ds8_digest(payload)


def _ds8_count(sources: Mapping[str, bytes], paths: Iterable[str]) -> dict[str, int]:
    selected = list(paths)
    return {
        "files": len(selected),
        "physical_lines": sum(sources[path].count(b"\n") for path in selected),
    }


def _ds8_snapshot(
    commit: str, sources: Mapping[str, bytes]
) -> dict[str, Any]:
    paths = sorted(sources)
    roles = {role: [path for path in paths if _ds8_role(path) == role] for role in (
        "production",
        "test",
        "story",
    )}
    features = {
        feature: {
            "all": _ds8_count(
                sources, [path for path in paths if _ds8_feature(path) == feature]
            ),
            "production": _ds8_count(
                sources,
                [
                    path
                    for path in roles["production"]
                    if _ds8_feature(path) == feature
                ],
            ),
            "tests": _ds8_count(
                sources,
                [path for path in roles["test"] if _ds8_feature(path) == feature],
            ),
            "stories": _ds8_count(
                sources,
                [path for path in roles["story"] if _ds8_feature(path) == feature],
            ),
        }
        for feature in ("runs", "artifacts", "evidence")
    }
    prefix = _ds8_coordinate_prefix()
    return {
        "commit": commit,
        "coordinate_prefix": prefix,
        "roots": list(DS8_STRANGLE_ROOTS),
        "extensions": list(DS8_STRANGLE_EXTENSIONS),
        "classifier": "stories_then_tests_then_production",
        "all": _ds8_count(sources, paths),
        "production": _ds8_count(sources, roles["production"]),
        "tests": _ds8_count(sources, roles["test"]),
        "stories": _ds8_count(sources, roles["story"]),
        "features": features,
        "path_manifest_sha256": _ds8_path_manifest(paths, prefix=prefix),
        "production_path_manifest_sha256": _ds8_path_manifest(
            roles["production"], prefix=prefix
        ),
        "content_manifest_sha256": _ds8_content_manifest(sources, paths),
    }


def _ds8_assignment(
    path: str,
    *,
    origin: str,
    disposition: str,
    cluster: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "path": path,
        "feature": _ds8_feature(path),
        "role": _ds8_role(path),
        "origin": origin,
        "disposition": disposition,
    }
    if cluster is not None:
        row["closure_cluster"] = cluster
    if disposition == "surface_out_of_scope":
        row.update(
            {
                "owner_team": "team-design",
                "capability_state": "surface_out_of_scope",
                "exit_condition": DS8_DEFERRED_EXIT_CONDITION,
                "successor_slice": None,
            }
        )
    return row


def build_ds8_strangle_coverage(
    *,
    baseline_commit: str,
    source_commit: str,
    writer_preimage_commit: str = DS8_STRANGLE_WRITER_HEAD_COMMIT,
    require_live_source_match: bool = False,
) -> dict[str, Any]:
    """Derive the complete DS8 assignment map from two independent Git walks."""
    baseline = _ds8_git_tree_sources(baseline_commit)
    source = _ds8_git_tree_sources(source_commit)
    if baseline != _ds8_archive_sources(baseline_commit):
        raise ValueError("DS8 baseline ls-tree/archive reconciliation failed")
    if source != _ds8_archive_sources(source_commit):
        raise ValueError("DS8 source ls-tree/archive reconciliation failed")
    ancestry = subprocess.run(  # noqa: S603 - fixed repository command
        ["git", "merge-base", "--is-ancestor", source_commit, writer_preimage_commit],  # noqa: S607
        cwd=REPO_ROOT.parent,
        check=False,
    )
    if ancestry.returncode != 0:
        raise ValueError("DS8 source freeze is not an ancestor of writer preimage")
    if require_live_source_match and source != _ds8_live_sources():
        raise ValueError("DS8 source-freeze/live-worktree byte reconciliation failed")
    if not set(baseline) <= set(source):
        raise ValueError(
            "DS8 source freeze removed opening paths: "
            + repr(sorted(set(baseline) - set(source)))
        )

    baseline_production = {
        path for path in baseline if _ds8_role(path) == "production"
    }
    if not DS8_STRANGLE_IN_SCOPE <= baseline_production:
        raise ValueError("DS8 declared in-scope path is absent from T0 production")
    deferred = baseline_production - DS8_STRANGLE_IN_SCOPE
    changed_baseline = sorted(
        path for path in baseline if baseline[path] != source[path]
    )
    changed_production = {
        path for path in changed_baseline if _ds8_role(path) == "production"
    }
    if changed_production != DS8_STRANGLE_IN_SCOPE:
        raise ValueError(
            "DS8 changed production set escaped the approved eight paths: "
            f"missing={sorted(DS8_STRANGLE_IN_SCOPE - changed_production)}:"
            f"extra={sorted(changed_production - DS8_STRANGLE_IN_SCOPE)}"
        )
    if any(baseline[path] != source[path] for path in deferred):
        raise ValueError("DS8 deferred production source changed after T0")

    cluster_by_path = {
        path: cluster
        for cluster, paths in DS8_STRANGLE_CLOSURE_PATHS.items()
        for path in paths
    }
    new_paths = sorted(set(source) - set(baseline))
    governed_mechanism_paths = DS8_STRANGLE_IN_SCOPE | {
        path for path in new_paths if _ds8_role(path) == "production"
    }
    if set(cluster_by_path) != governed_mechanism_paths:
        raise ValueError("DS8 closure receipts do not partition mechanism paths")

    assignments: list[dict[str, Any]] = []
    for path in sorted(baseline):
        role = _ds8_role(path)
        if path in DS8_STRANGLE_IN_SCOPE:
            disposition = "in_scope"
        elif role == "production":
            disposition = "surface_out_of_scope"
        elif role == "test":
            disposition = "verification_companion"
        else:
            disposition = "retained"
        assignments.append(
            _ds8_assignment(
                path,
                origin="opening_base",
                disposition=disposition,
                cluster=cluster_by_path.get(path),
            )
        )
    assignments.extend(
        _ds8_assignment(
            path,
            origin="source_freeze",
            disposition="new_in_slice",
            cluster=cluster_by_path.get(path),
        )
        for path in new_paths
    )
    closure_receipts = [
        {
            "cluster": cluster,
            "source_commit": source_commit,
            "paths": list(paths),
            "file_count": len(paths),
            "path_content_manifest_sha256": _ds8_content_manifest(source, paths),
        }
        for cluster, paths in DS8_STRANGLE_CLOSURE_PATHS.items()
    ]
    prefix = _ds8_coordinate_prefix()
    return {
        "coverage_id": "ds8-case-evidence-strangle-coverage",
        "predicate_provenance": "independently_reconciled",
        "family_complete": False,
        "baseline": _ds8_snapshot(baseline_commit, baseline),
        "source_freeze": _ds8_snapshot(source_commit, source),
        "writer_preimage_commit": writer_preimage_commit,
        "opening_production_partition": {
            "total": len(baseline_production),
            "in_scope": len(DS8_STRANGLE_IN_SCOPE),
            "deferred": len(deferred),
            "in_scope_path_manifest_sha256": _ds8_path_manifest(
                DS8_STRANGLE_IN_SCOPE, prefix=prefix
            ),
            "deferred_path_manifest_sha256": _ds8_path_manifest(
                deferred, prefix=prefix
            ),
            "deferred_unchanged_content_manifest_sha256": _ds8_content_manifest(
                baseline, deferred
            ),
        },
        "new_path_count": len(new_paths),
        "new_path_manifest_sha256": _ds8_path_manifest(new_paths, prefix=prefix),
        "changed_baseline_paths": changed_baseline,
        "assignments": assignments,
        "closure_receipts": closure_receipts,
        "reconciliation": {
            "baseline_git_tree_vs_archive": "exact",
            "source_git_tree_vs_archive": "exact",
            "source_freeze_vs_writer_history": "ancestor",
            "live_tree_disposition": "outside_frozen_coverage",
        },
    }


def validate_ds8_strangle_coverage(
    coverage: Mapping[str, Any],
    *,
    expected_baseline_commit: str = DS8_STRANGLE_BASE_COMMIT,
    expected_source_commit: str = DS8_STRANGLE_SOURCE_COMMIT,
) -> list[str]:
    """Reject every missing, duplicate, stale, or nonexistent DS8 row."""
    try:
        expected = build_ds8_strangle_coverage(
            baseline_commit=expected_baseline_commit,
            source_commit=expected_source_commit,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return [f"ds8_strangle_reconciliation_failed:{exc}"]
    assignments = coverage.get("assignments")
    if not isinstance(assignments, list):
        return ["ds8_strangle_assignments_missing"]
    expected_rows = {row["path"]: row for row in expected["assignments"]}
    actual_paths = [
        str(row.get("path", ""))
        for row in assignments
        if isinstance(row, Mapping)
    ]
    counts = Counter(actual_paths)
    errors: list[str] = []
    errors.extend(
        f"ds8_strangle_duplicate_assignment:{path}"
        for path, count in sorted(counts.items())
        if count > 1
    )
    errors.extend(
        f"ds8_strangle_missing_assignment:{path}"
        for path in sorted(set(expected_rows) - set(actual_paths))
    )
    errors.extend(
        f"ds8_strangle_nonexistent_assignment:{path}"
        for path in sorted(set(actual_paths) - set(expected_rows))
    )
    actual_by_path = {
        str(row.get("path")): row
        for row in assignments
        if isinstance(row, Mapping) and counts[str(row.get("path"))] == 1
    }
    errors.extend(
        f"ds8_strangle_stale_assignment:{path}"
        for path in sorted(set(expected_rows) & set(actual_by_path))
        if actual_by_path[path] != expected_rows[path]
    )
    for key, expected_value in expected.items():
        if key == "assignments":
            continue
        if coverage.get(key) != expected_value:
            errors.append(f"ds8_strangle_metadata_stale:{key}")
    errors.extend(
        f"ds8_strangle_unknown_property:{key}"
        for key in sorted(set(coverage) - set(expected))
    )
    return errors


def ds8_strangle_corruption_probes(
    coverage: Mapping[str, Any],
    *,
    expected_baseline_commit: str = DS8_STRANGLE_BASE_COMMIT,
    expected_source_commit: str = DS8_STRANGLE_SOURCE_COMMIT,
) -> list[str]:
    """Return named DS8 mutations that escaped the generic validator."""
    probes: list[tuple[str, dict[str, Any], str]] = []
    first_path = str(coverage["assignments"][0]["path"])

    missing = copy.deepcopy(coverage)
    removed = missing["assignments"].pop(0)
    probes.append(
        (
            "missing",
            missing,
            f"ds8_strangle_missing_assignment:{removed['path']}",
        )
    )
    duplicate = copy.deepcopy(coverage)
    duplicate["assignments"].append(copy.deepcopy(duplicate["assignments"][0]))
    probes.append(
        (
            "duplicate",
            duplicate,
            f"ds8_strangle_duplicate_assignment:{first_path}",
        )
    )
    stale = copy.deepcopy(coverage)
    stale["assignments"][0]["disposition"] = "new_in_slice"
    probes.append(
        ("stale", stale, f"ds8_strangle_stale_assignment:{first_path}")
    )
    nonexistent = copy.deepcopy(coverage)
    nonexistent["assignments"][0]["path"] = (
        "apps/runtime-dashboard/src/features/runs/nonexistent.ts"
    )
    probes.append(
        (
            "nonexistent",
            nonexistent,
            "ds8_strangle_nonexistent_assignment:"
            "apps/runtime-dashboard/src/features/runs/nonexistent.ts",
        )
    )
    deferred_index = next(
        index
        for index, row in enumerate(coverage["assignments"])
        if row["disposition"] == "surface_out_of_scope"
    )
    deferred_path = str(coverage["assignments"][deferred_index]["path"])
    for field, value in (
        ("owner_team", "team-runtime"),
        ("capability_state", "implemented_but_not_orchestrated"),
        ("exit_condition", "count_reaches_zero"),
        ("successor_slice", "DS9"),
    ):
        mutation = copy.deepcopy(coverage)
        mutation["assignments"][deferred_index][field] = value
        probes.append(
            (
                f"deferred-{field}",
                mutation,
                f"ds8_strangle_stale_assignment:{deferred_path}",
            )
        )
    removed_property = copy.deepcopy(coverage)
    removed_property.pop("closure_receipts")
    probes.append(
        (
            "remove-property-keep-counts",
            removed_property,
            "ds8_strangle_metadata_stale:closure_receipts",
        )
    )
    failures: list[str] = []
    for name, mutation, expected_error in probes:
        errors = validate_ds8_strangle_coverage(
            mutation,
            expected_baseline_commit=expected_baseline_commit,
            expected_source_commit=expected_source_commit,
        )
        if expected_error not in errors:
            failures.append(name)
    return failures


def build_ds8b_post_freeze_transition(
    *,
    baseline_commit: str,
    source_commit: str,
    historical_coverage: Mapping[str, Any],
    require_live_source_match: bool = False,
) -> dict[str, Any]:
    """Derive only DS8-B's post-C07 delta without rewriting C07 history."""
    historical_errors = validate_ds8_strangle_coverage(historical_coverage)
    if historical_errors:
        raise ValueError(
            "DS8-B historical coverage is not exact: "
            + ";".join(historical_errors)
        )
    historical_assignments = list(historical_coverage["assignments"])
    historical_deferred = [
        row
        for row in historical_assignments
        if row["disposition"] == "surface_out_of_scope"
    ]
    if len(historical_assignments) != 217 or len(historical_deferred) != 137:
        raise ValueError("DS8-B historical 217/137 denominator drift")

    baseline = _ds8_git_tree_sources(baseline_commit)
    source = _ds8_git_tree_sources(source_commit)
    if baseline != _ds8_archive_sources(baseline_commit):
        raise ValueError("DS8-B baseline ls-tree/archive reconciliation failed")
    if source != _ds8_archive_sources(source_commit):
        raise ValueError("DS8-B source ls-tree/archive reconciliation failed")
    ancestry = subprocess.run(  # noqa: S603 - fixed repository command
        ["git", "merge-base", "--is-ancestor", baseline_commit, source_commit],  # noqa: S607
        cwd=REPO_ROOT.parent,
        check=False,
    )
    if ancestry.returncode != 0:
        raise ValueError("DS8-B source freeze does not descend from its base")
    if require_live_source_match and source != _ds8_live_sources():
        raise ValueError("DS8-B source-freeze/live-worktree byte reconciliation failed")

    removed_paths = sorted(set(baseline) - set(source))
    if removed_paths:
        raise ValueError(f"DS8-B source freeze removed paths: {removed_paths}")
    changed_existing_paths = sorted(
        path
        for path in set(baseline) & set(source)
        if baseline[path] != source[path]
    )
    new_paths = sorted(set(source) - set(baseline))
    transition_paths = sorted([*changed_existing_paths, *new_paths])
    rows = []
    for path in transition_paths:
        role = _ds8_role(path)
        is_new = path in new_paths
        if is_new:
            disposition = "new_in_slice"
        elif role == "production":
            disposition = "in_scope_rebound"
        elif role == "test":
            disposition = "verification_companion_rebound"
        else:
            disposition = "retained_rebound"
        rows.append(
            {
                "path": path,
                "feature": _ds8_feature(path),
                "role": role,
                "origin": "source_freeze" if is_new else "opening_base",
                "disposition": disposition,
                "closure_cluster": "C03",
                "baseline_content_sha256": (
                    None if is_new else _ds8_digest(baseline[path])
                ),
                "source_content_sha256": _ds8_digest(source[path]),
            }
        )
    prefix = _ds8_coordinate_prefix()
    return {
        "coverage_id": "ds8b-case-workspace-post-freeze-transition",
        "predicate_provenance": "independently_reconciled",
        "transition_complete": True,
        "baseline": _ds8_snapshot(baseline_commit, baseline),
        "source_freeze": _ds8_snapshot(source_commit, source),
        "historical_binding": {
            "coverage_id": historical_coverage["coverage_id"],
            "coverage_sha256": _ds8_json_digest(historical_coverage),
            "assignment_count": len(historical_assignments),
            "assignment_path_manifest_sha256": _ds8_path_manifest(
                (str(row["path"]) for row in historical_assignments),
                prefix=prefix,
            ),
            "deferred_count": len(historical_deferred),
            "deferred_rows_sha256": _ds8_json_digest(historical_deferred),
        },
        "changed_existing_path_count": len(changed_existing_paths),
        "new_path_count": len(new_paths),
        "transition_path_count": len(transition_paths),
        "transition_path_manifest_sha256": _ds8_path_manifest(
            transition_paths, prefix=prefix
        ),
        "assignments": rows,
        "closure_receipt": {
            "cluster": "C03",
            "source_commit": source_commit,
            "paths": transition_paths,
            "file_count": len(transition_paths),
            "path_content_manifest_sha256": _ds8_content_manifest(
                source, transition_paths
            ),
        },
        "reconciliation": {
            "baseline_git_tree_vs_archive": "exact",
            "source_git_tree_vs_archive": "exact",
            "baseline_vs_source_history": "ancestor",
            "historical_217_map": "byte_preserved",
            "historical_137_deferrals": "byte_preserved",
            "live_tree_disposition": "outside_frozen_transition",
        },
    }


def validate_ds8b_post_freeze_transition(
    transition: Mapping[str, Any],
    historical_coverage: Mapping[str, Any],
    *,
    expected_baseline_commit: str = DS8B_TRANSITION_BASE_COMMIT,
    expected_source_commit: str = DS8B_TRANSITION_SOURCE_COMMIT,
) -> list[str]:
    """Reject missing, duplicate, stale, or nonexistent DS8-B rows."""
    try:
        expected = build_ds8b_post_freeze_transition(
            baseline_commit=expected_baseline_commit,
            source_commit=expected_source_commit,
            historical_coverage=historical_coverage,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return [f"ds8b_transition_reconciliation_failed:{exc}"]
    assignments = transition.get("assignments")
    if not isinstance(assignments, list):
        return ["ds8b_transition_assignments_missing"]
    expected_rows = {row["path"]: row for row in expected["assignments"]}
    actual_paths = [
        str(row.get("path", ""))
        for row in assignments
        if isinstance(row, Mapping)
    ]
    counts = Counter(actual_paths)
    errors: list[str] = []
    errors.extend(
        f"ds8b_transition_duplicate_assignment:{path}"
        for path, count in sorted(counts.items())
        if count > 1
    )
    errors.extend(
        f"ds8b_transition_missing_assignment:{path}"
        for path in sorted(set(expected_rows) - set(actual_paths))
    )
    errors.extend(
        f"ds8b_transition_nonexistent_assignment:{path}"
        for path in sorted(set(actual_paths) - set(expected_rows))
    )
    actual_by_path = {
        str(row.get("path")): row
        for row in assignments
        if isinstance(row, Mapping) and counts[str(row.get("path"))] == 1
    }
    errors.extend(
        f"ds8b_transition_stale_assignment:{path}"
        for path in sorted(set(expected_rows) & set(actual_by_path))
        if actual_by_path[path] != expected_rows[path]
    )
    for key, expected_value in expected.items():
        if key == "assignments":
            continue
        if transition.get(key) != expected_value:
            errors.append(f"ds8b_transition_metadata_stale:{key}")
    errors.extend(
        f"ds8b_transition_unknown_property:{key}"
        for key in sorted(set(transition) - set(expected))
    )
    return errors


def ds8b_post_freeze_corruption_probes(
    transition: Mapping[str, Any],
    historical_coverage: Mapping[str, Any],
    *,
    expected_baseline_commit: str = DS8B_TRANSITION_BASE_COMMIT,
    expected_source_commit: str = DS8B_TRANSITION_SOURCE_COMMIT,
) -> list[str]:
    """Return named DS8-B mutations that escaped its generic validator."""
    first_path = str(transition["assignments"][0]["path"])
    probes: list[tuple[str, dict[str, Any], str]] = []
    missing = copy.deepcopy(transition)
    removed = missing["assignments"].pop(0)
    probes.append(
        (
            "missing",
            missing,
            f"ds8b_transition_missing_assignment:{removed['path']}",
        )
    )
    duplicate = copy.deepcopy(transition)
    duplicate["assignments"].append(copy.deepcopy(duplicate["assignments"][0]))
    probes.append(
        (
            "duplicate",
            duplicate,
            f"ds8b_transition_duplicate_assignment:{first_path}",
        )
    )
    stale = copy.deepcopy(transition)
    stale["assignments"][0]["source_content_sha256"] = "sha256:" + "0" * 64
    probes.append(
        ("stale", stale, f"ds8b_transition_stale_assignment:{first_path}")
    )
    nonexistent = copy.deepcopy(transition)
    nonexistent["assignments"][0]["path"] = (
        "apps/runtime-dashboard/src/features/runs/nonexistent-ds8b.ts"
    )
    probes.append(
        (
            "nonexistent",
            nonexistent,
            "ds8b_transition_nonexistent_assignment:"
            "apps/runtime-dashboard/src/features/runs/nonexistent-ds8b.ts",
        )
    )
    historical = copy.deepcopy(transition)
    historical["historical_binding"]["deferred_rows_sha256"] = (
        "sha256:" + "0" * 64
    )
    probes.append(
        (
            "historical-deferrals",
            historical,
            "ds8b_transition_metadata_stale:historical_binding",
        )
    )
    failures: list[str] = []
    for name, mutation, expected_error in probes:
        errors = validate_ds8b_post_freeze_transition(
            mutation,
            historical_coverage,
            expected_baseline_commit=expected_baseline_commit,
            expected_source_commit=expected_source_commit,
        )
        if expected_error not in errors:
            failures.append(name)
    return failures


def _ds8b_register_candidate_text(
    original_text: str, transition: Mapping[str, Any]
) -> str:
    """Surgically add DS8-B's transition while preserving C07 byte history."""
    original = json.loads(original_text)
    candidate = original_text
    old_version = (
        '{\n  "$schema": "./frontend-disposition-register.schema.json",\n'
        '  "schema_version": "1.1",'
    )
    new_version = (
        '{\n  "$schema": "./frontend-disposition-register.schema.json",\n'
        '  "schema_version": "1.2",'
    )
    if candidate.count(old_version) == 1:
        candidate = candidate.replace(old_version, new_version, 1)
    elif candidate.count(new_version) != 1:
        raise ValueError("DS8-B register schema-version preimage is ambiguous")

    key_marker = '  "ds8b_post_freeze_transition": '
    rendered = json.dumps(transition, indent=2, ensure_ascii=False).replace(
        "\n", "\n  "
    )
    if key_marker in candidate:
        if candidate.count(key_marker) != 1:
            raise ValueError("DS8-B transition key is duplicated")
        value_start = candidate.index(key_marker) + len(key_marker)
        _stored, relative_end = json.JSONDecoder().raw_decode(
            candidate[value_start:]
        )
        candidate = (
            candidate[:value_start]
            + rendered
            + candidate[value_start + relative_end :]
        )
    else:
        insertion_marker = '  "seeded_negative_lifecycle": ['
        if candidate.count(insertion_marker) != 1:
            raise ValueError("DS8-B register insertion point is ambiguous")
        candidate = candidate.replace(
            insertion_marker,
            key_marker + rendered + ",\n" + insertion_marker,
            1,
        )
    parsed = json.loads(candidate)
    if parsed.get("ds8b_post_freeze_transition") != transition:
        raise ValueError("DS8-B transition surgical insertion changed value")
    original_without = copy.deepcopy(original)
    original_without.pop("ds8b_post_freeze_transition", None)
    original_without["schema_version"] = "1.2"
    candidate_without = copy.deepcopy(parsed)
    candidate_without.pop("ds8b_post_freeze_transition", None)
    if candidate_without != original_without:
        raise ValueError("DS8-B writer changed an unrelated register value")
    return candidate


def _ds8_register_candidate_text(
    original_text: str, coverage: Mapping[str, Any]
) -> str:
    """Surgically add or refresh only the DS8 coverage and schema version."""
    original = json.loads(original_text)
    candidate = original_text
    old_version = (
        '{\n  "$schema": "./frontend-disposition-register.schema.json",\n'
        '  "schema_version": "1.0",'
    )
    new_version = (
        '{\n  "$schema": "./frontend-disposition-register.schema.json",\n'
        '  "schema_version": "1.1",'
    )
    if candidate.count(old_version) == 1:
        candidate = candidate.replace(old_version, new_version, 1)
    elif candidate.count(new_version) != 1:
        raise ValueError("DS8 register schema-version preimage is ambiguous")

    key_marker = '  "ds8_strangle_coverage": '
    rendered = json.dumps(coverage, indent=2, ensure_ascii=False).replace(
        "\n", "\n  "
    )
    if key_marker in candidate:
        if candidate.count(key_marker) != 1:
            raise ValueError("DS8 coverage key is duplicated")
        value_start = candidate.index(key_marker) + len(key_marker)
        _stored, relative_end = json.JSONDecoder().raw_decode(
            candidate[value_start:]
        )
        candidate = (
            candidate[:value_start]
            + rendered
            + candidate[value_start + relative_end :]
        )
    else:
        insertion_marker = '  "seeded_negative_lifecycle": ['
        if candidate.count(insertion_marker) != 1:
            raise ValueError("DS8 register insertion point is ambiguous")
        candidate = candidate.replace(
            insertion_marker,
            key_marker + rendered + ",\n" + insertion_marker,
            1,
        )
    parsed = json.loads(candidate)
    if parsed.get("ds8_strangle_coverage") != coverage:
        raise ValueError("DS8 coverage surgical insertion changed value")
    original_without_ds8 = copy.deepcopy(original)
    original_without_ds8.pop("ds8_strangle_coverage", None)
    original_without_ds8["schema_version"] = "1.1"
    candidate_without_ds8 = copy.deepcopy(parsed)
    candidate_without_ds8.pop("ds8_strangle_coverage", None)
    if candidate_without_ds8 != original_without_ds8:
        raise ValueError("DS8 coverage writer changed an unrelated register value")
    return candidate


def _replace_unique_text(
    text: str, *, old: str, new: str, label: str
) -> str:
    if text.count(old) == 1:
        return text.replace(old, new, 1)
    if text.count(new) == 1:
        return text
    raise ValueError(f"DS8 status preimage is ambiguous: {label}")


def _baseline_manifest_content_candidate_text(
    original_text: str,
    *,
    reanchors: frozenset[tuple[str, str]],
    owner: str,
) -> str:
    """Surgically re-anchor an owner's exact lint-resolution source receipts."""
    match = re.search(
        r'^    "resolution_content_bindings":\s*(\[)',
        original_text,
        re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"{owner} baseline resolution bindings are missing")
    array_start = match.start(1)
    array_end = _json_container_end(original_text, array_start)
    index = array_start + 1
    spans: list[tuple[tuple[str, str], int, int, Mapping[str, Any]]] = []
    while index < array_end:
        while index < array_end and (
            original_text[index].isspace() or original_text[index] == ","
        ):
            index += 1
        if index >= array_end:
            break
        if original_text[index] != "{":
            raise ValueError(f"{owner} baseline resolution row is malformed")
        object_end = _json_container_end(original_text, index)
        row = json.loads(original_text[index : object_end + 1])
        key = (str(row.get("cluster_id")), str(row.get("path")))
        spans.append((key, index, object_end, row))
        index = object_end + 1

    counts = Counter(key for key, _start, _end, _row in spans)
    if any(counts[key] != 1 for key in reanchors):
        raise ValueError(f"{owner} baseline resolution target cardinality drift")
    replacements: list[tuple[int, int, str]] = []
    for key, object_start, object_end, row in spans:
        if key not in reanchors:
            continue
        source_path = REPO_ROOT / key[1]
        if not source_path.is_file():
            raise ValueError(f"{owner} baseline source is missing: {key[1]}")
        old = f'"sha256": "{row["sha256"]}"'
        new = f'"sha256": "{hashlib.sha256(source_path.read_bytes()).hexdigest()}"'
        object_text = original_text[object_start : object_end + 1]
        if object_text.count(old) != 1:
            raise ValueError(f"{owner} baseline hash span is ambiguous: {key}")
        relative_start = object_text.index(old)
        replacements.append(
            (
                object_start + relative_start,
                object_start + relative_start + len(old),
                new,
            )
        )
    candidate = original_text
    for start, end, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:start] + replacement + candidate[end:]
    candidate_data = json.loads(candidate)
    errors = validate_baseline_manifest(candidate_data)
    if errors:
        raise ValueError(f"{owner} baseline candidate rejected: " + ";".join(errors))
    return candidate


def _ds8_baseline_manifest_candidate_text(original_text: str) -> str:
    """Re-anchor exactly three DS8-touched lint-resolution source receipts."""
    return _baseline_manifest_content_candidate_text(
        original_text,
        reanchors=DS8_BASELINE_CONTENT_REANCHORS,
        owner="DS8",
    )


def _ds10_baseline_manifest_candidate_text(original_text: str) -> str:
    """Re-anchor exactly four DS10-touched lint-resolution source receipts."""
    return _baseline_manifest_content_candidate_text(
        original_text,
        reanchors=DS10_BASELINE_CONTENT_REANCHORS,
        owner="DS10",
    )


def _ds8_status_inventory_candidate_text(
    original_text: str, *, register_bytes: bytes
) -> str:
    """Re-anchor four exact DS8-induced status receipts without reformatting."""
    stored = json.loads(original_text)
    generated = stored["sources"]["generated_client"]
    candidate = _replace_unique_text(
        original_text,
        old=f'"canonical_sha256": "{generated["canonical_sha256"]}"',
        new=(
            '"canonical_sha256": "'
            + _sha256(REPO_ROOT / generated["canonical_path"])
            + '"'
        ),
        label="generated canonical hash",
    )
    candidate = _replace_unique_text(
        candidate,
        old=f'"types_sha256": "{generated["types_sha256"]}"',
        new=(
            '"types_sha256": "'
            + _sha256(REPO_ROOT / generated["types_path"])
            + '"'
        ),
        label="generated types hash",
    )
    candidate = _replace_unique_text(
        candidate,
        old=(
            '"path": "apps/runtime-dashboard/src/features/evidence/components/'
            'DataIntelligencePanel.tsx",\n          "line": 1211,\n'
            '          "kind": "prop"'
        ),
        new=(
            '"path": "apps/runtime-dashboard/src/features/evidence/components/'
            'DataIntelligencePanel.tsx",\n          "line": 1212,\n'
            '          "kind": "prop"'
        ),
        label="DataIntelligencePanel consumer line",
    )
    stored = json.loads(candidate)
    old_register_hash = str(stored["sources"]["ds19"]["sha256"])
    new_register_hash = _ds8_digest(register_bytes)
    candidate = _replace_unique_text(
        candidate,
        old=f'"sha256": "{old_register_hash}"',
        new=f'"sha256": "{new_register_hash}"',
        label="DS19 register hash",
    )
    parsed = json.loads(candidate)
    if parsed["sources"]["ds19"]["sha256"] != new_register_hash:
        raise ValueError("DS8 status register hash did not bind candidate bytes")
    return candidate


def _c13_status_inventory_candidate_text(
    original_text: str, *, register_bytes: bytes
) -> str:
    """Re-anchor only the register source induced by the C13 root transition."""
    stored = json.loads(original_text)
    old_register_hash = str(stored["sources"]["ds19"]["sha256"])
    new_register_hash = _ds8_digest(register_bytes)
    candidate = _replace_unique_text(
        original_text,
        old=f'"sha256": "{old_register_hash}"',
        new=f'"sha256": "{new_register_hash}"',
        label="C13 DS19 register hash",
    )
    parsed = json.loads(candidate)
    if parsed["sources"]["ds19"]["sha256"] != new_register_hash:
        raise ValueError("C13 status register hash did not bind candidate bytes")
    expected = copy.deepcopy(stored)
    expected["sources"]["ds19"]["sha256"] = new_register_hash
    if parsed != expected:
        raise ValueError("C13 status candidate changed an unrelated value")
    return candidate


def _status_line_leaf_count(value: Any, path: tuple[str, ...] = ()) -> int:
    governed_keys = {
        "line",
        "start_line",
        "end_line",
        "canonical_line",
        "schema_line",
    }
    governed_inline = {
        ("denominators", "current_inline"),
        ("denominators", "ds1_inline"),
    }
    if isinstance(value, Mapping):
        return sum(
            (
                1
                if type(child) is int  # noqa: E721 - bool must be excluded
                and (key in governed_keys or path + (str(key),) in governed_inline)
                else _status_line_leaf_count(child, path + (str(key),))
            )
            for key, child in value.items()
        )
    if isinstance(value, list):
        return sum(
            _status_line_leaf_count(child, path + (str(index),))
            for index, child in enumerate(value)
        )
    return 0


def _string_leaf_count(value: Any, marker: str) -> int:
    if isinstance(value, Mapping):
        return sum(_string_leaf_count(child, marker) for child in value.values())
    if isinstance(value, list):
        return sum(_string_leaf_count(child, marker) for child in value)
    return int(isinstance(value, str) and marker in value)


def _ds8_status_candidate_errors(
    inventory: Mapping[str, Any], *, register_bytes: bytes
) -> list[str]:
    errors = status_checker._schema_errors(  # type: ignore[attr-defined]
        inventory,
        status_checker.INVENTORY_SCHEMA_PATH,
        "status-retirement-inventory",
    )
    if inventory["sources"]["ds19"]["sha256"] != _ds8_digest(register_bytes):
        errors.append("ds8_status_register_candidate_hash_drift")
    generated = inventory["sources"]["generated_client"]
    for key in ("canonical", "types"):
        source_path = REPO_ROOT / generated[f"{key}_path"]
        if generated[f"{key}_sha256"] != _sha256(source_path):
            errors.append(f"ds8_status_generated_{key}_hash_drift")
    if _status_line_leaf_count(inventory) != 387:
        errors.append("ds8_status_line_leaf_count_drift")
    if _string_leaf_count(inventory, "#ts-identity=") != 30:
        errors.append("ds8_status_ts_identity_count_drift")
    status_row = next(
        row
        for row in inventory["entries"]
        if row["unit_id"] == "status-inline-review-surface"
    )
    data_consumer = next(
        row
        for row in status_row["consumers"]
        if row["path"].endswith("/DataIntelligencePanel.tsx")
    )
    if data_consumer["line"] != 1212:
        errors.append("ds8_status_DataIntelligencePanel_line_drift")
    return errors


def _stage_same_directory(path: Path, payload: bytes) -> Path:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.ds8-", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary)
    owned_descriptor = descriptor
    try:
        os.fchmod(owned_descriptor, path.stat().st_mode & 0o7777)
        handle = os.fdopen(owned_descriptor, "wb", closefd=True)
        owned_descriptor = -1
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        if owned_descriptor >= 0:
            os.close(owned_descriptor)
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _failure_atomic_write_texts(
    candidates: Mapping[Path, str],
    *,
    validate_after: Callable[[], Sequence[str]],
    pre_promote: Callable[[], None] | None = None,
) -> None:
    """Promote a prevalidated family and restore it on handled failure."""
    ordered = list(candidates)
    originals = {path: path.read_bytes() for path in ordered}
    staged: dict[Path, Path] = {}
    rollback: dict[Path, Path] = {}
    promoted: list[Path] = []
    try:
        for path in ordered:
            staged[path] = _stage_same_directory(
                path, candidates[path].encode("utf-8")
            )
        for path in ordered:
            rollback[path] = _stage_same_directory(path, originals[path])
        if pre_promote is not None:
            pre_promote()
        for path in ordered:
            os.replace(staged[path], path)
            promoted.append(path)
            _fsync_directory(path.parent)
        post_errors = list(validate_after())
        if post_errors:
            raise ValueError("DS8 post-promotion validation failed: " + ";".join(post_errors))
    except BaseException as original_error:
        rollback_errors: list[str] = []
        for path in reversed(promoted):
            try:
                os.replace(rollback[path], path)
                _fsync_directory(path.parent)
            except BaseException as rollback_error:  # pragma: no cover - hard stop
                rollback_errors.append(
                    f"{path}:{rollback_error}:recovery={rollback[path]}"
                )
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        if rollback_errors:
            raise RuntimeError(
                "DS8 rollback incomplete; readable recovery files retained: "
                + ";".join(rollback_errors)
            ) from original_error
        for temporary in rollback.values():
            temporary.unlink(missing_ok=True)
        raise
    for temporary in staged.values():
        temporary.unlink(missing_ok=True)
    for temporary in rollback.values():
        temporary.unlink(missing_ok=True)


def _historical_register_projection(
    data: Mapping[str, Any],
    *,
    top_level_fields: Sequence[str] = (),
    supplemental_finding_ids: Collection[str] = (),
) -> dict[str, Any]:
    """Project only a historical writer's owned values into today's register.

    Historical surgical writers separately prove that every peer byte is
    preserved.  Their semantic/schema check must therefore judge the values
    they own without making the historical preimage responsible for required
    fields and live receipts introduced by later slices.
    """
    projected = copy.deepcopy(_load_json(REGISTER_PATH))
    for field in top_level_fields:
        if field not in data:
            raise ValueError(f"historical projection field missing:{field}")
        projected[field] = copy.deepcopy(data[field])

    finding_ids = set(supplemental_finding_ids)
    if finding_ids:
        candidate_rows = {
            str(row.get("finding_id")): copy.deepcopy(row)
            for row in data.get("supplemental_findings", [])
            if isinstance(row, Mapping)
            and str(row.get("finding_id")) in finding_ids
        }
        if set(candidate_rows) != finding_ids:
            raise ValueError("historical projection finding cardinality drift")
        live_rows = projected.get("supplemental_findings")
        if not isinstance(live_rows, list):
            raise ValueError("historical projection live finding container drift")
        replaced: set[str] = set()
        for index, row in enumerate(live_rows):
            if not isinstance(row, Mapping):
                continue
            finding_id = str(row.get("finding_id"))
            if finding_id in candidate_rows:
                live_rows[index] = candidate_rows[finding_id]
                replaced.add(finding_id)
        if replaced != finding_ids:
            raise ValueError("historical projection live finding cardinality drift")
    return projected


def _historical_register_projection_schema_errors(
    data: Mapping[str, Any],
    *,
    top_level_fields: Sequence[str] = (),
) -> list[str]:
    """Validate historical owned fields inside the complete live schema context."""
    try:
        projected = _historical_register_projection(
            data,
            top_level_fields=top_level_fields,
        )
    except ValueError as exc:
        return [str(exc)]
    return _schema_errors(projected, SCHEMA_PATH)


def _ds11_trust_presentation_candidate_errors(
    data: Mapping[str, Any],
    *,
    report_parity: bool,
) -> list[str]:
    """Validate C04-owned rows in today's complete register context."""
    try:
        projected = _historical_register_projection(
            data,
            supplemental_finding_ids=DS11_TRUST_PRESENTATION_FINDING_IDS,
        )
    except ValueError as exc:
        return [f"DS11 C04 candidate projection rejected:{exc}"]
    errors = validate_register(
        projected,
        live_probes=False,
        report_parity=report_parity,
    )
    expected = list(DS10_DECLARED_EXTERNAL_REGISTER_NONCLOSURES)
    if Counter(errors) == Counter(expected):
        return []
    return [
        "DS11 C04 candidate error set drift:"
        + json.dumps(sorted(errors), ensure_ascii=False)
    ]


def _write_ds11_trust_presentation_family() -> dict[str, int]:
    """Atomically repair the two C04 rows and their report under one lock."""
    with _ds11_trust_presentation_register_lock():
        original_texts = {
            REGISTER_PATH: REGISTER_PATH.read_text(encoding="utf-8"),
            REPORT_PATH: REPORT_PATH.read_text(encoding="utf-8"),
        }
        original_sources = {
            REPO_ROOT / source_path: (REPO_ROOT / source_path).read_bytes()
            for source_path in DS11_C04_MECHANISM_PATHS
        }
        scan = _authority_presentation_scan()
        register_candidate = _ds11_trust_presentation_transition_text(
            original_texts[REGISTER_PATH],
            scan=scan,
        )
        preservation_errors = _ds11_trust_presentation_preservation_errors(
            original_texts[REGISTER_PATH], register_candidate
        )
        if preservation_errors:
            raise ValueError(
                "DS11 C04 register candidate rejected:"
                + ";".join(preservation_errors)
            )
        register_data = json.loads(register_candidate)
        pre_errors = _ds11_trust_presentation_candidate_errors(
            register_data,
            report_parity=False,
        )
        if pre_errors:
            raise ValueError(";".join(pre_errors))
        report_candidate = _ds11_trust_presentation_report_transition_text(
            original_texts[REPORT_PATH],
            opening_register_text=original_texts[REGISTER_PATH],
            candidate_register_text=register_candidate,
        )
        candidates = {
            REGISTER_PATH: register_candidate,
            REPORT_PATH: report_candidate,
        }

        def validate_after() -> list[str]:
            errors: list[str] = []
            for governed_path, expected_text in candidates.items():
                if governed_path.read_text(encoding="utf-8") != expected_text:
                    errors.append(
                        "ds11_trust_presentation_family_readback_drift:"
                        + str(governed_path)
                    )
            errors.extend(
                _ds11_trust_presentation_candidate_errors(
                    _load_json(REGISTER_PATH),
                    report_parity=True,
                )
            )
            for source_path, expected_bytes in original_sources.items():
                if source_path.read_bytes() != expected_bytes:
                    errors.append(
                        "ds11_trust_presentation_source_readback_drift:"
                        + str(source_path)
                    )
            return errors

        def final_pre_promote_fence() -> None:
            for governed_path, expected_text in original_texts.items():
                if governed_path.read_text(encoding="utf-8") != expected_text:
                    raise ValueError(
                        "DS11 C04 governed preimage moved before promotion:"
                        + str(governed_path)
                    )
            for source_path, expected_bytes in original_sources.items():
                if source_path.read_bytes() != expected_bytes:
                    raise ValueError(
                        "DS11 C04 source moved before promotion:" + str(source_path)
                    )

        _failure_atomic_write_texts(
            candidates,
            validate_after=validate_after,
            pre_promote=final_pre_promote_fence,
        )
        return {
            "authority_findings": len(DS11_TRUST_PRESENTATION_FINDING_IDS),
            "mechanism_paths": len(DS11_C04_MECHANISM_PATHS),
        }


def _c13_writer_fence() -> None:
    """Require the bound branch, clean governed family, and a free index."""
    branch = _c03_git_text("symbolic-ref", "-q", "HEAD").strip()
    if branch != "refs/heads/codex/atlas-ds6-final-closure":
        raise ValueError(f"C13 writer branch fence failed: {branch}")
    head = _c03_git_text("rev-parse", "HEAD").strip()
    ancestry = subprocess.run(  # noqa: S603 - fixed Git command
        [  # noqa: S607
            "git",
            "merge-base",
            "--is-ancestor",
            C13_VERIFIED_REVISION,
            head,
        ],
        cwd=REPO_ROOT.parent,
        check=False,
    )
    if ancestry.returncode != 0:
        raise ValueError("C13 verified revision is not an ancestor of writer HEAD")
    tracked_status = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=no",
            "--",
            *(
                str(path.relative_to(REPO_ROOT))
                for path in (
                    REGISTER_PATH,
                    REPORT_PATH,
                    STATUS_INVENTORY_PATH,
                    BASELINE_PATH,
                    DS1_PATH,
                )
            ),
        ],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if tracked_status.returncode != 0 or tracked_status.stdout:
        raise ValueError("C13 writer requires a clean governed family")
    index_lock_ref = _c03_git_text("rev-parse", "--git-path", "index.lock").strip()
    index_lock = Path(index_lock_ref)
    if not index_lock.is_absolute():
        index_lock = REPO_ROOT.parent / index_lock
    if index_lock.exists():
        raise ValueError(f"C13 writer index lock is live: {index_lock}")


def _c13_status_receipt(
    inventory: Mapping[str, Any], debt: Mapping[str, Any]
) -> tuple[int, int, str]:
    diagnostics = status_checker.validate_inventory(inventory, debt)
    payload = "".join(f"{diagnostic}\n" for diagnostic in diagnostics).encode()
    return len(diagnostics), len(payload), hashlib.sha256(payload).hexdigest()


def _c13_status_candidate_errors(
    inventory: Mapping[str, Any], *, register_bytes: bytes
) -> list[str]:
    """Validate a status candidate against the register bytes promoted with it."""
    errors = status_checker._schema_errors(  # type: ignore[attr-defined]
        inventory,
        status_checker.INVENTORY_SCHEMA_PATH,
        "status-retirement-inventory",
    )
    if inventory["sources"]["ds19"]["sha256"] != _ds8_digest(register_bytes):
        errors.append("c13_status_register_candidate_hash_drift")
    return errors


def _ds9_c07_writer_fence(
    candidate_texts: Mapping[Path, str],
) -> None:
    """Require DS9's attached branch, one admitted family state, and a free index."""
    branch = _c03_git_text("symbolic-ref", "-q", "HEAD").strip()
    if branch != "refs/heads/codex/ds9-human-decision-integrity-plan":
        raise ValueError(f"DS9 C07 writer branch fence failed: {branch}")
    if set(candidate_texts) != set(DS9_C07_OPENING_FAMILY_SHA256):
        raise ValueError("DS9 C07 writer candidate family denominator drift")

    observed = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in DS9_C07_OPENING_FAMILY_SHA256
    }
    candidate_hashes = {
        path: hashlib.sha256(candidate_texts[path].encode("utf-8")).hexdigest()
        for path in candidate_texts
    }
    admitted_states = (
        DS9_C07_OPENING_FAMILY_SHA256,
        DS9_C07_SUPERSEDED_FAMILY_SHA256,
        candidate_hashes,
    )
    if not any(
        all(observed[path] == expected[path] for path in candidate_texts)
        for expected in admitted_states
    ):
        raise ValueError("DS9 C07 governed family is mixed or has unknown bytes")

    index_lock_ref = _c03_git_text("rev-parse", "--git-path", "index.lock").strip()
    index_lock = Path(index_lock_ref)
    if not index_lock.is_absolute():
        index_lock = REPO_ROOT.parent / index_lock
    if index_lock.exists():
        raise ValueError(f"DS9 C07 writer found live index lock: {index_lock}")


def _write_ds9_human_decision_integrity_family() -> dict[str, int]:
    """Atomically adjudicate DS9 roots, authority rows, report, and status anchor."""
    original_texts = {
        REGISTER_PATH: REGISTER_PATH.read_text(encoding="utf-8"),
        REPORT_PATH: REPORT_PATH.read_text(encoding="utf-8"),
        STATUS_INVENTORY_PATH: STATUS_INVENTORY_PATH.read_text(encoding="utf-8"),
    }
    original_sources = {path: path.read_bytes() for path in DS9_C07_AUTHORITY_SOURCE_PATHS}
    scan = _authority_presentation_scan()
    register_candidate = _ds9_c07_register_candidate_text(
        original_texts[REGISTER_PATH],
        scan=scan,
    )
    register_data = json.loads(register_candidate)
    pre_errors = validate_register(
        register_data,
        live_probes=False,
        report_parity=False,
    )
    if pre_errors:
        raise ValueError("DS9 C07 register candidate rejected: " + ";".join(pre_errors))
    report_candidate = render_report(register_data)
    status_candidate = _c13_status_inventory_candidate_text(
        original_texts[STATUS_INVENTORY_PATH],
        register_bytes=register_candidate.encode("utf-8"),
    )
    status_errors = _c13_status_candidate_errors(
        json.loads(status_candidate),
        register_bytes=register_candidate.encode("utf-8"),
    )
    if status_errors:
        raise ValueError("DS9 C07 status candidate rejected: " + ";".join(status_errors))
    candidates = {
        REGISTER_PATH: register_candidate,
        REPORT_PATH: report_candidate,
        STATUS_INVENTORY_PATH: status_candidate,
    }
    _ds9_c07_writer_fence(candidates)
    for path, original_text in original_texts.items():
        if path.read_text(encoding="utf-8") != original_text:
            raise ValueError(f"DS9 C07 governed preimage moved: {path}")
    for path, original_bytes in original_sources.items():
        if path.read_bytes() != original_bytes:
            raise ValueError(f"DS9 C07 authority source moved: {path}")

    def validate_after() -> list[str]:
        errors: list[str] = []
        for path, expected_text in candidates.items():
            if path.read_text(encoding="utf-8") != expected_text:
                errors.append(f"ds9_c07_family_readback_drift:{path}")
        errors.extend(validate_register(_load_json(REGISTER_PATH)))
        errors.extend(
            _c13_status_candidate_errors(
                _load_json(STATUS_INVENTORY_PATH),
                register_bytes=REGISTER_PATH.read_bytes(),
            )
        )
        for path, expected_bytes in original_sources.items():
            if path.read_bytes() != expected_bytes:
                errors.append(f"ds9_c07_authority_source_readback_drift:{path}")
        return errors

    def final_pre_promote_fence() -> None:
        _ds9_c07_writer_fence(candidates)
        for path, expected_text in original_texts.items():
            if path.read_text(encoding="utf-8") != expected_text:
                raise ValueError(f"DS9 C07 governed preimage moved before promotion: {path}")
        for path, expected_bytes in original_sources.items():
            if path.read_bytes() != expected_bytes:
                raise ValueError(f"DS9 C07 authority source moved before promotion: {path}")

    _failure_atomic_write_texts(
        candidates,
        validate_after=validate_after,
        pre_promote=final_pre_promote_fence,
    )
    return {
        "root_objects": len(DS9_C07_ROOT_SCOPE),
        "authority_findings": len(DS9_C07_AUTHORITY_FINDING_IDS),
        "objects": len(DS9_C07_ROOT_SCOPE) + len(DS9_C07_AUTHORITY_FINDING_IDS),
    }


def _write_c13_print_family() -> dict[str, Any]:
    """Atomically transition the print root, report, and induced status anchor."""
    _c13_writer_fence()
    journal_path = (
        REPO_ROOT
        / "docs/plans/active/atlas-slices/DS6-evidence-workflow-journal.md"
    )
    original_journal = journal_path.read_text(encoding="utf-8")
    receipt = _c13_independent_print_receipt(original_journal)
    evidence_paths = {
        *(str(row["path"]) for row in receipt["source_bindings"]),
        *(str(row["path"]) for row in receipt["raw_artifacts"]),
        str(receipt["environment_probe_producer"]["path"]),
    }
    original_evidence = {
        REPO_ROOT / source_ref: (REPO_ROOT / source_ref).read_bytes()
        for source_ref in evidence_paths
    }
    original_register = REGISTER_PATH.read_text(encoding="utf-8")
    original_report = REPORT_PATH.read_text(encoding="utf-8")
    original_status = STATUS_INVENTORY_PATH.read_text(encoding="utf-8")
    original_baseline = BASELINE_PATH.read_text(encoding="utf-8")
    original_readiness = DS1_PATH.read_text(encoding="utf-8")
    original_texts = {
        REGISTER_PATH: original_register,
        REPORT_PATH: original_report,
        STATUS_INVENTORY_PATH: original_status,
    }
    register_candidate = _c13_print_transition_text(
        original_register,
        receipt=receipt,
    )
    register_data = json.loads(register_candidate)
    pre_errors = validate_register(
        register_data, live_probes=False, report_parity=False
    )
    if pre_errors:
        raise ValueError("C13 register candidate rejected: " + ";".join(pre_errors))
    report_candidate = render_report(register_data)
    status_candidate = _c13_status_inventory_candidate_text(
        original_status,
        register_bytes=register_candidate.encode("utf-8"),
    )
    status_data = json.loads(status_candidate)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    expected_status = (
        13,
        887,
        "511bfd68fea9232d15e33a577859121ca61501a4824a8535ccfd16551ffa17f9",
    )
    status_errors = _c13_status_candidate_errors(
        status_data,
        register_bytes=register_candidate.encode("utf-8"),
    )
    if status_errors:
        raise ValueError("C13 status candidate rejected: " + ";".join(status_errors))
    if _c13_status_receipt(json.loads(original_status), debt) != expected_status:
        raise ValueError("C13 opening status diagnostic identity drift")
    if BASELINE_PATH.read_text(encoding="utf-8") != original_baseline:
        raise ValueError("C13 baseline moved while building candidates")
    if DS1_PATH.read_text(encoding="utf-8") != original_readiness:
        raise ValueError("C13 readiness ledger moved while building candidates")

    candidates = {
        REGISTER_PATH: register_candidate,
        REPORT_PATH: report_candidate,
        STATUS_INVENTORY_PATH: status_candidate,
    }

    def validate_after() -> list[str]:
        errors: list[str] = []
        for governed_path, expected_text in candidates.items():
            if governed_path.read_text(encoding="utf-8") != expected_text:
                errors.append(f"c13_family_readback_drift:{governed_path}")
        errors.extend(validate_register(_load_json(REGISTER_PATH), live_probes=False))
        if _c13_status_receipt(_load_json(STATUS_INVENTORY_PATH), debt) != (
            expected_status
        ):
            errors.append("c13_status_diagnostic_identity_drift")
        if BASELINE_PATH.read_text(encoding="utf-8") != original_baseline:
            errors.append("c13_baseline_readback_drift")
        if DS1_PATH.read_text(encoding="utf-8") != original_readiness:
            errors.append("c13_readiness_readback_drift")
        if journal_path.read_text(encoding="utf-8") != original_journal:
            errors.append("c13_receipt_readback_drift")
        for evidence_path, expected_bytes in original_evidence.items():
            if evidence_path.read_bytes() != expected_bytes:
                errors.append(f"c13_evidence_readback_drift:{evidence_path}")
        return errors

    def final_pre_promote_fence() -> None:
        _c13_writer_fence()
        for governed_path, expected_text in original_texts.items():
            if governed_path.read_text(encoding="utf-8") != expected_text:
                raise ValueError(
                    f"C13 governed preimage moved before promotion: {governed_path}"
                )
        if BASELINE_PATH.read_text(encoding="utf-8") != original_baseline:
            raise ValueError("C13 baseline moved before promotion")
        if DS1_PATH.read_text(encoding="utf-8") != original_readiness:
            raise ValueError("C13 readiness ledger moved before promotion")
        if journal_path.read_text(encoding="utf-8") != original_journal:
            raise ValueError("C13 receipt moved before promotion")
        for evidence_path, expected_bytes in original_evidence.items():
            if evidence_path.read_bytes() != expected_bytes:
                raise ValueError(
                    f"C13 evidence moved before promotion: {evidence_path}"
                )

    _failure_atomic_write_texts(
        candidates,
        validate_after=validate_after,
        pre_promote=final_pre_promote_fence,
    )
    return receipt


def _ds8_writer_fence() -> None:
    branch = _ds8_git_text("symbolic-ref", "-q", "HEAD").strip()
    if branch != "refs/heads/codex/atlas-ds8-planning":
        raise ValueError(f"DS8 writer branch fence failed: {branch}")
    head = _ds8_git_text("rev-parse", "HEAD").strip()
    if head != DS8_STRANGLE_WRITER_HEAD_COMMIT:
        raise ValueError(f"DS8 writer source HEAD drift: {head}")
    for ancestor, label in (
        (DS8_STRANGLE_BASE_COMMIT, "immutable base"),
        (DS8_STRANGLE_SOURCE_COMMIT, "source freeze"),
    ):
        ancestry = subprocess.run(  # noqa: S603 - fixed repository command
            ["git", "merge-base", "--is-ancestor", ancestor, head],  # noqa: S607
            cwd=REPO_ROOT.parent,
            check=False,
        )
        if ancestry.returncode != 0:
            raise ValueError(f"DS8 {label} is not an ancestor of writer HEAD")
    source_status = subprocess.run(  # noqa: S603 - fixed repository command
        [  # noqa: S607 - controlled toolchain executable
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *DS8_STRANGLE_ROOTS,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if source_status.returncode != 0 or source_status.stdout:
        raise ValueError("DS8 source roots changed after C06 freeze")


def _write_ds8_strangle_family() -> dict[str, Any]:
    """Materialize baseline, register, report, and status in one lock window."""
    _ds8_writer_fence()
    coverage = build_ds8_strangle_coverage(
        baseline_commit=DS8_STRANGLE_BASE_COMMIT,
        source_commit=DS8_STRANGLE_SOURCE_COMMIT,
        writer_preimage_commit=DS8_STRANGLE_WRITER_HEAD_COMMIT,
    )
    original_register = REGISTER_PATH.read_text(encoding="utf-8")
    original_report = REPORT_PATH.read_text(encoding="utf-8")
    original_status = STATUS_INVENTORY_PATH.read_text(encoding="utf-8")
    original_baseline = BASELINE_PATH.read_text(encoding="utf-8")
    opening_hashes = {
        REGISTER_PATH: "sha256:4cc97abd7e0984e6dea28f77c5f046a34709e768a141aa5bb08c44cd371b8b61",
        REPORT_PATH: "sha256:b2e25ddea0169c6b3643c88e53fbc4d28798e8a5427cf9619b3aecb008cca36d",
        STATUS_INVENTORY_PATH: "sha256:9a6eddd187bd20bf88f773f944e7f717480d9a9c1750e7c79fad29ee60aca8b5",
        BASELINE_PATH: "sha256:e060069e7fcae2226b332634338da1be96348c29390d1498080ba87cfa33d5c5",
    }
    original_texts = {
        REGISTER_PATH: original_register,
        REPORT_PATH: original_report,
        STATUS_INVENTORY_PATH: original_status,
        BASELINE_PATH: original_baseline,
    }
    baseline_candidate = _ds8_baseline_manifest_candidate_text(
        original_baseline
    )
    baseline_data = json.loads(baseline_candidate)
    refreshed_register = _refresh_supplemental_findings_text(original_register)
    register_candidate = _ds8_register_candidate_text(
        refreshed_register, coverage
    )
    register_data = json.loads(register_candidate)
    pre_errors = validate_register(
        register_data,
        report_parity=False,
        baseline_manifest=baseline_data,
    )
    if pre_errors:
        raise ValueError("DS8 register candidate rejected: " + ";".join(pre_errors))
    report_candidate = render_report(register_data)
    status_candidate = _ds8_status_inventory_candidate_text(
        original_status, register_bytes=register_candidate.encode("utf-8")
    )
    pre_errors.extend(
        _ds8_status_candidate_errors(
            json.loads(status_candidate),
            register_bytes=register_candidate.encode("utf-8"),
        )
    )
    if pre_errors:
        raise ValueError("DS8 family candidate rejected: " + ";".join(pre_errors))
    candidates = {
        REGISTER_PATH: register_candidate,
        REPORT_PATH: report_candidate,
        STATUS_INVENTORY_PATH: status_candidate,
        BASELINE_PATH: baseline_candidate,
    }
    for path, original in original_texts.items():
        original_hash = _ds8_digest(original.encode("utf-8"))
        candidate_hash = _ds8_digest(candidates[path].encode("utf-8"))
        if original_hash not in {opening_hashes[path], candidate_hash}:
            raise ValueError(f"DS8 governed preimage drift: {path}")

    def validate_after() -> list[str]:
        errors: list[str] = []
        for path, expected_text in candidates.items():
            if path.read_text(encoding="utf-8") != expected_text:
                errors.append(f"ds8_family_readback_drift:{path}")
        stored_register = _load_json(REGISTER_PATH)
        errors.extend(validate_register(stored_register))
        stored_status = _load_json(STATUS_INVENTORY_PATH)
        debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
        diagnostics = status_checker.validate_inventory(stored_status, debt)
        receipt = "".join(f"{diagnostic}\n" for diagnostic in diagnostics).encode()
        if len(diagnostics) != 13:
            errors.append(f"ds8_status_diagnostic_count:{len(diagnostics)}")
        if len(receipt) != 887:
            errors.append(f"ds8_status_diagnostic_bytes:{len(receipt)}")
        if hashlib.sha256(receipt).hexdigest() != (
            "511bfd68fea9232d15e33a577859121ca61501a4824a8535ccfd16551ffa17f9"
        ):
            errors.append("ds8_status_diagnostic_identity_drift")
        return errors

    def final_pre_promote_fence() -> None:
        _ds8_writer_fence()
        for path, expected_text in original_texts.items():
            if path.read_text(encoding="utf-8") != expected_text:
                raise ValueError(f"DS8 governed preimage moved before promotion: {path}")

    _failure_atomic_write_texts(
        candidates,
        validate_after=validate_after,
        pre_promote=final_pre_promote_fence,
    )
    return coverage


def _ds8b_writer_fence() -> None:
    """Require DS8-B's branch, source freeze, clean family, and free index."""
    branch = _ds8_git_text("symbolic-ref", "-q", "HEAD").strip()
    if branch != "refs/heads/codex/atlas-ds8-b-case-workspace":
        raise ValueError(f"DS8-B writer branch fence failed: {branch}")
    head = _ds8_git_text("rev-parse", "HEAD").strip()
    ancestry = subprocess.run(  # noqa: S603 - fixed Git command
        [  # noqa: S607 - controlled toolchain executable
            "git",
            "merge-base",
            "--is-ancestor",
            DS8B_TRANSITION_SOURCE_COMMIT,
            head,
        ],
        cwd=REPO_ROOT.parent,
        check=False,
    )
    if ancestry.returncode != 0:
        raise ValueError("DS8-B source freeze is not an ancestor of writer HEAD")
    source = _ds8_git_tree_sources(DS8B_TRANSITION_SOURCE_COMMIT)
    if source != _ds8_live_sources():
        raise ValueError("DS8-B feature roots changed after C03 source freeze")
    governed_paths = (
        REGISTER_PATH,
        SCHEMA_PATH,
        REPORT_PATH,
        STATUS_INVENTORY_PATH,
        BASELINE_PATH,
        DS1_PATH,
        Path(__file__).resolve(),
        ATLAS_DIR / "test_frontend_disposition_register.py",
    )
    tracked_status = subprocess.run(  # noqa: S603 - fixed Git command
        [  # noqa: S607 - controlled toolchain executable
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=no",
            "--",
            *(str(path.relative_to(REPO_ROOT)) for path in governed_paths),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if tracked_status.returncode != 0 or tracked_status.stdout:
        raise ValueError("DS8-B writer requires a clean governed family")
    index_lock_ref = _ds8_git_text("rev-parse", "--git-path", "index.lock").strip()
    index_lock = Path(index_lock_ref)
    if not index_lock.is_absolute():
        index_lock = REPO_ROOT.parent / index_lock
    if index_lock.exists():
        raise ValueError(f"DS8-B writer found live index lock: {index_lock}")


def _write_ds8b_transition_family() -> dict[str, Any]:
    """Atomically bind the post-C07 transition without rewriting C07 rows."""
    _ds8b_writer_fence()
    original_register = REGISTER_PATH.read_text(encoding="utf-8")
    original_report = REPORT_PATH.read_text(encoding="utf-8")
    original_status = STATUS_INVENTORY_PATH.read_text(encoding="utf-8")
    original_baseline = BASELINE_PATH.read_text(encoding="utf-8")
    original_readiness = DS1_PATH.read_text(encoding="utf-8")
    opening_hashes = {
        REGISTER_PATH: (
            "sha256:c1181a07efc38273aa4b4ec1c6f46a1f"
            "183c1e197b67b96c8796d575da75be11"
        ),
        REPORT_PATH: (
            "sha256:1bc9a2d378ca42dbe7721769ede7369b"
            "bbef1a88ecc0939e36201663df1c6dde"
        ),
        STATUS_INVENTORY_PATH: (
            "sha256:42b6ac0dd5e1cf9614570357c5dbaed1"
            "5a2a814ce40227fb047ad974284cd1e2"
        ),
    }
    original_texts = {
        REGISTER_PATH: original_register,
        REPORT_PATH: original_report,
        STATUS_INVENTORY_PATH: original_status,
    }
    for path, original in original_texts.items():
        if _ds8_digest(original.encode("utf-8")) != opening_hashes[path]:
            raise ValueError(f"DS8-B governed preimage drift: {path}")

    register_data = json.loads(original_register)
    historical = register_data["ds8_strangle_coverage"]
    transition = build_ds8b_post_freeze_transition(
        baseline_commit=DS8B_TRANSITION_BASE_COMMIT,
        source_commit=DS8B_TRANSITION_SOURCE_COMMIT,
        historical_coverage=historical,
        require_live_source_match=True,
    )
    register_candidate = _ds8b_register_candidate_text(
        original_register, transition
    )
    candidate_data = json.loads(register_candidate)
    pre_errors = validate_register(
        candidate_data,
        live_probes=False,
        report_parity=False,
    )
    if pre_errors:
        raise ValueError("DS8-B register candidate rejected: " + ";".join(pre_errors))
    report_candidate = render_report(candidate_data)
    status_candidate = _ds8_status_inventory_candidate_text(
        original_status,
        register_bytes=register_candidate.encode("utf-8"),
    )
    status_data = json.loads(status_candidate)
    debt = status_checker._load_json(status_checker.WAIST_DEBT_PATH)
    expected_status = (
        13,
        887,
        "511bfd68fea9232d15e33a577859121ca61501a4824a8535ccfd16551ffa17f9",
    )
    status_errors = _ds8_status_candidate_errors(
        status_data,
        register_bytes=register_candidate.encode("utf-8"),
    )
    if status_errors:
        raise ValueError(
            "DS8-B status candidate rejected: " + ";".join(status_errors)
        )
    opening_diagnostics = status_checker.validate_inventory(
        json.loads(original_status), debt
    )
    regeneration_drifts = {
        "inventory_source_hash_drift:packages/runtime-api-client/"
        "canonicalRuntimeApiClient.ts",
        "inventory_source_hash_drift:packages/runtime-api-client/types.ts",
    }
    if not regeneration_drifts <= set(opening_diagnostics):
        raise ValueError("DS8-B opening generated-source diagnostic mapping drift")
    inherited_diagnostics = [
        diagnostic
        for diagnostic in opening_diagnostics
        if diagnostic not in regeneration_drifts
    ]
    inherited_payload = "".join(
        f"{diagnostic}\n" for diagnostic in inherited_diagnostics
    ).encode()
    inherited_status = (
        len(inherited_diagnostics),
        len(inherited_payload),
        hashlib.sha256(inherited_payload).hexdigest(),
    )
    if inherited_status != expected_status:
        raise ValueError(
            "DS8-B opening status receipt is not inherited 13 plus the two "
            "mapped generated-source drifts"
        )
    if BASELINE_PATH.read_text(encoding="utf-8") != original_baseline:
        raise ValueError("DS8-B baseline moved while building candidates")
    if DS1_PATH.read_text(encoding="utf-8") != original_readiness:
        raise ValueError("DS8-B readiness ledger moved while building candidates")

    candidates = {
        REGISTER_PATH: register_candidate,
        REPORT_PATH: report_candidate,
        STATUS_INVENTORY_PATH: status_candidate,
    }

    def validate_after() -> list[str]:
        errors: list[str] = []
        for path, expected_text in candidates.items():
            if path.read_text(encoding="utf-8") != expected_text:
                errors.append(f"ds8b_family_readback_drift:{path}")
        errors.extend(validate_register(_load_json(REGISTER_PATH)))
        if _c13_status_receipt(_load_json(STATUS_INVENTORY_PATH), debt) != (
            expected_status
        ):
            errors.append("ds8b_status_diagnostic_identity_drift")
        if BASELINE_PATH.read_text(encoding="utf-8") != original_baseline:
            errors.append("ds8b_baseline_readback_drift")
        if DS1_PATH.read_text(encoding="utf-8") != original_readiness:
            errors.append("ds8b_readiness_readback_drift")
        return errors

    def final_pre_promote_fence() -> None:
        _ds8b_writer_fence()
        for path, expected_text in original_texts.items():
            if path.read_text(encoding="utf-8") != expected_text:
                raise ValueError(
                    f"DS8-B governed preimage moved before promotion: {path}"
                )
        if BASELINE_PATH.read_text(encoding="utf-8") != original_baseline:
            raise ValueError("DS8-B baseline moved before promotion")
        if DS1_PATH.read_text(encoding="utf-8") != original_readiness:
            raise ValueError("DS8-B readiness ledger moved before promotion")

    _failure_atomic_write_texts(
        candidates,
        validate_after=validate_after,
        pre_promote=final_pre_promote_fence,
    )
    return transition


def _path_from_ref(value: str) -> Path:
    path_text = value.split("#", 1)[0]
    match = re.match(r"^(.*?):\d+(?::\d+)?$", path_text)
    if match:
        path_text = match.group(1)
    return REPO_ROOT / path_text


def _reference_resolution_error(value: str) -> str | None:
    path = _path_from_ref(value)
    if not path.exists():
        return f"reference_path_missing:{value}"
    path_text = value.split("#", 1)[0]
    match = re.match(r"^(.*?):(\d+)(?::\d+)?$", path_text)
    if match and path.is_file():
        line_number = int(match.group(2))
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_number < 1 or line_number > line_count:
            return f"reference_line_out_of_bounds:{value}:{line_count}"
    return None


def _typescript_identity_reference_errors(
    references: Sequence[str], *, source_root: Path | None = None
) -> list[str]:
    """Batch-validate every stored C21a identity against one source snapshot."""
    parsed: list[tuple[str, dict[str, Any]]] = []
    for reference in references:
        if "#ts-identity=" not in reference:
            continue
        try:
            payload = _typescript_reference_identity_payload(reference)
        except (KeyError, ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError):
            return ["typescript_reference_identity_invalid"]
        parsed.append((reference, payload))
    if not parsed:
        return []
    root = source_root or REPO_ROOT
    source_paths = {str(payload["source_path"]) for _reference, payload in parsed}
    sources = {
        source_path: (root / source_path).read_text(encoding="utf-8")
        for source_path in source_paths
        if (root / source_path).is_file()
    }
    requests = [
        {
            "sourcePath": payload["source_path"],
            "role": payload["role"],
            "discriminator": payload["discriminator"],
        }
        for _reference, payload in parsed
    ]
    errors: list[str] = []
    for reference, payload, facts in zip(
        (reference for reference, _payload in parsed),
        (payload for _reference, payload in parsed),
        _typescript_reference_construct_facts_batch(
            sources,
            requests,
            closed_universe=source_root is not None,
        ),
        strict=True,
    ):
        error = _typescript_reference_match_error(payload, facts)
        if error is not None:
            errors.append(f"{error}:{reference}")
    return errors


def _structured_identity_reference_errors(references: Sequence[str]) -> list[str]:
    """Validate every stored C21c selector identity against its live document."""
    errors: list[str] = []
    for reference in references:
        if "#structured-identity=" not in reference:
            continue
        path_prefix = reference.split("#structured-identity=", 1)[0]
        if not _is_canonical_repo_relative_source_path(path_prefix):
            errors.append(f"structured_reference_source_path_invalid:{reference}")
            continue
        path = REPO_ROOT / path_prefix
        sources = (
            {path_prefix: path.read_text(encoding="utf-8")}
            if path.is_file()
            else {}
        )
        errors.extend(
            f"{error}:{reference}"
            for error in _validate_structured_reference_identity(
                {"encoded_identity": reference}, sources
            )
        )
    return errors


_C21B_DESCRIPTOR_HINTS = {
    "packages/runtime-api-client/canonicalRuntimeApiClient.ts:958": ("exported_declaration", "RunSummary"),
    "packages/runtime-api-client/types.ts:10012": ("type_property", "components.RunSummary"),
    "packages/runtime-api-client/types.ts:10031": ("type_property", "components.finished_at"),
    "packages/runtime-api-client/types.ts:10058": ("type_property", "components.status"),
    "apps/runtime-dashboard/src/features/runs/api/useDepthNCycleBoardProjection.ts:156": ("exported_declaration", "depthNCycleBoardProjectionQueryOptions"),
    "packages/runtime-api-client/types.ts:2446": ("type_property", "components.AuthMeResponse"),
    "apps/runtime-dashboard/src/api/hooks/useAuthMe.ts:42": ("named_declaration", "fetchAuthMe"),
    "apps/runtime-dashboard/src/api/queryKeys.ts:11": ("variable_declaration", "queryKeys"),
    "apps/runtime-dashboard/src/features/composer/state/composerDraftRepository.ts:15": ("exported_declaration", "ComposerDraftRecord"),
    "apps/runtime-dashboard/src/app/offline/composerDraftDb.ts:13": (
        "exported_declaration",
        "deleteComposerDraftRecord",
    ),
    "apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx:301": ("named_declaration", "writeStoredCausalDraft"),
    "apps/runtime-dashboard/src/features/runs/domain/disputes.ts:109": ("exported_declaration", "writeStoredDisputes"),
    "apps/runtime-dashboard/src/features/runs/domain/operatorCraft.ts:444": ("exported_declaration", "setReviewerThreshold"),
    "packages/runtime-api-client/types.ts:2462": ("type_property", "components.permissions"),
    "apps/runtime-dashboard/src/api/types.ts:2513": ("type_property", "components.permissions"),
}


def _c21c_structured_identity_literals() -> dict[str, str]:
    """Return the five live C21c identities; line hints are migration-only."""
    identities: dict[str, str] = {}
    for reference, (
        format_adapter,
        selector,
        _value_sha256,
    ) in _C21C_STRUCTURED_HINTS.items():
        source_path, _line = reference.rsplit(":", 1)
        source = (REPO_ROOT / source_path).read_text(encoding="utf-8")
        identity = _structured_reference_identity(
            {source_path: source},
            source_path=source_path,
            format_adapter=format_adapter,
            selector=selector,
        )
        if identity["encoded_identity"] != _C21C_FROZEN_STRUCTURED_IDENTITIES[reference]:
            raise ValueError(f"c21c_structured_source_drift:{reference}")
        identities[reference] = identity["encoded_identity"]
    return identities


def _c21b_descriptor_identity_literals() -> dict[str, str]:
    """Return the 15 static descriptor identities; line hints are creation-only."""
    anchors = []
    for reference, (role, discriminator) in _C21B_DESCRIPTOR_HINTS.items():
        path, line = reference.rsplit(":", 1)
        anchors.append({"path": path, "line": int(line), "role": role, "discriminator": discriminator})
    identities = _typescript_reference_identities_from_anchors(anchors)
    return {reference: identity["encoded_identity"] for reference, identity in zip(_C21B_DESCRIPTOR_HINTS, identities, strict=True)}


def _c21b_identity_anchor(reference: str) -> dict[str, Any] | None:
    """Return the explicit direct-syntax role for a gated TypeScript reference."""
    if reference in _C21B_DESCRIPTOR_HINTS:
        role, discriminator = _C21B_DESCRIPTOR_HINTS[reference]
        path, line = reference.rsplit(":", 1)
        return {"path": path, "line": int(line), "role": role, "discriminator": discriminator}
    match = re.match(r"^(.*?):(\d+)$", reference)
    if not match or Path(match.group(1)).suffix not in {".ts", ".tsx"}:
        return None
    source_line = (REPO_ROOT / match.group(1)).read_text(encoding="utf-8").splitlines()[
        int(match.group(2)) - 1
    ]
    route_match = re.search(
        r'["\'](/?public/decisions/:signedId)["\']', source_line
    )
    if route_match:
        role, discriminator = "string_literal", route_match.group(1)
    elif declaration_match := re.search(
        r"\b(?P<export>export\s+)?(?:async\s+)?function\s+"
        r"(?P<name>(?:build|verify)SignedPublicDecisionPacket)\b",
        source_line,
    ):
        role = (
            "exported_declaration"
            if declaration_match.group("export")
            else "named_declaration"
        )
        discriminator = declaration_match.group("name")
    elif "buildSignedPublicDecisionPacket" in source_line:
        role, discriminator = "call_expression", "buildSignedPublicDecisionPacket"
    elif "verifySignedPublicDecisionPacket" in source_line:
        role, discriminator = "call_expression", "verifySignedPublicDecisionPacket"
    else:
        return None
    return {"path": match.group(1), "line": int(match.group(2)), "role": role, "discriminator": discriminator}


def _c21b_surgical_identity_text(text: str) -> str:
    """Replace only gated observed/evidence reference string spans, backwards."""
    data = json.loads(text)
    identity_counts_before = (
        sum(
            "#ts-identity=" in ref
            for census in data["reference_censuses"]
            for probe in census["probes"]
            for ref in probe["observed_refs"]
        ),
        sum(
            "#ts-identity=" in ref
            for finding in data["supplemental_findings"]
            if "authority_sink" in finding
            for ref in finding["evidence_refs"]
        ),
        sum(
            "#ts-identity=" in ref
            for finding in data["supplemental_findings"]
            if "authority_sink" not in finding
            for ref in finding["evidence_refs"]
        ),
    )
    migration_counts = [0, 0, 0]
    anchors: list[dict[str, Any]] = []
    references: list[str] = []
    for census in data["reference_censuses"]:
        for probe in census["probes"]:
            for reference in probe["observed_refs"]:
                anchor = _c21b_identity_anchor(reference)
                if anchor:
                    anchors.append(anchor)
                    references.append(reference)
                    migration_counts[0] += 1
    for finding in data["supplemental_findings"]:
        if "authority_sink" in finding:
            sink = finding["authority_sink"]
            component = sink["component_declaration"]
            authority_anchors = {
                f"{component['path']}:{component['line']}": {
                    "path": component["path"], "line": component["line"], "role": "named_declaration", "discriminator": sink["component"]
                }
            }
            consumer_role = "jsx_attribute" if sink["sink_kind"] == "prop_boundary" else "jsx_opening"
            for site in sink["consumer_sites"]:
                authority_anchors[f"{site['path']}:{site['line']}"] = {
                    "path": site["path"], "line": site["line"], "role": consumer_role,
                    "discriminator": sink.get("prop", "Badge") if consumer_role == "jsx_attribute" else "Badge",
                }
            for reference in finding["evidence_refs"]:
                anchor = authority_anchors.get(reference)
                if anchor:
                    anchors.append(anchor)
                    references.append(reference)
                    migration_counts[1] += 1
            continue
        for reference in finding["evidence_refs"]:
            anchor = _c21b_identity_anchor(reference)
            if anchor:
                anchors.append(anchor)
                references.append(reference)
                migration_counts[2] += 1
    identities = _typescript_reference_identities_from_anchors(anchors)
    replacements = {
        reference: identity["encoded_identity"]
        for reference, identity in zip(references, identities, strict=True)
    }
    expected_occurrences = Counter(references)
    replacements_at: list[tuple[int, int, str]] = []
    for reference, identity in replacements.items():
        needle = json.dumps(reference, ensure_ascii=False)
        positions = [match.start() for match in re.finditer(re.escape(needle), text)]
        if len(positions) != expected_occurrences[reference]:
            raise ValueError(f"c21b_surgical_reference_span_ambiguous:{reference}")
        replacements_at.extend(
            (position, position + len(needle), json.dumps(identity, ensure_ascii=False))
            for position in positions
        )
    migrated = text
    for start, end, replacement in sorted(replacements_at, reverse=True):
        migrated = migrated[:start] + replacement + migrated[end:]
    migrated_data = json.loads(migrated)
    observed = [
        ref
        for census in migrated_data["reference_censuses"]
        for probe in census["probes"]
        for ref in probe["observed_refs"]
        if "#ts-identity=" in ref
    ]
    authority = [
        ref
        for finding in migrated_data["supplemental_findings"]
        if "authority_sink" in finding
        for ref in finding["evidence_refs"]
        if "#ts-identity=" in ref
    ]
    descriptors = [
        ref
        for finding in migrated_data["supplemental_findings"]
        if "authority_sink" not in finding
        for ref in finding["evidence_refs"]
        if "#ts-identity=" in ref
    ]
    expected_partition = tuple(
        existing + migrated
        for existing, migrated in zip(
            identity_counts_before, migration_counts, strict=True
        )
    )
    if (len(observed), len(authority), len(descriptors)) != expected_partition:
        raise ValueError("c21b_identity_partition_drift")
    return migrated


def _c21c_surgical_identity_text(text: str) -> str:
    """Refresh only governed descriptors and prove the C21c residual partition."""
    if _c21c_structured_identity_literals() != _C21C_FROZEN_STRUCTURED_IDENTITIES:
        raise ValueError("c21c_frozen_structured_identity_drift")
    migrated = _refresh_supplemental_findings_text(text)
    data = json.loads(migrated)
    references = [
        reference
        for finding in data["supplemental_findings"]
        for reference in finding["evidence_refs"]
    ]
    references.extend(
        reference
        for census in data["reference_censuses"]
        for probe in census["probes"]
        for reference in probe["observed_refs"]
    )
    structured = [
        reference
        for reference in references
        if "#structured-identity=" in reference
    ]
    if len(structured) != 5 or set(structured) != set(
        _C21C_FROZEN_STRUCTURED_IDENTITIES.values()
    ):
        raise ValueError("c21c_structured_identity_partition_drift")
    if any(reference in references for reference in _C21C_STRUCTURED_HINTS):
        raise ValueError("c21c_legacy_structured_line_reference")
    line_reference_re = re.compile(r"^(.*?):\d+(?::\d+)?$")
    line_references = [
        reference for reference in references if line_reference_re.match(reference)
    ]
    if len(line_references) != 12 or len(
        {
            line_reference_re.match(reference).group(1)
            for reference in line_references
        }
    ) != 10:
        raise ValueError("c21c_navigation_residual_drift")
    if any(
        Path(line_reference_re.match(reference).group(1)).suffix
        in {".json", ".toml"}
        for reference in line_references
    ):
        raise ValueError("c21c_structured_line_reference_residual")
    return migrated


def _probe_observation_matches_stored_mode(
    stored: Sequence[str], observed: Sequence[str]
) -> tuple[bool | None, str | None]:
    """Compare a live probe with its committed legacy or C21d identity mode."""
    identity_flags = ["#ts-identity=" in reference for reference in stored]
    if not any(identity_flags):
        return list(observed) == list(stored), None
    if not all(identity_flags):
        return None, "census_identity_mode_mixed"
    anchors = []
    for reference in observed:
        anchor = _c21b_identity_anchor(reference)
        if anchor is None:
            return None, f"census_identity_observation_unmappable:{reference}"
        anchors.append(anchor)
    try:
        stored_identities = [
            _typescript_reference_identity_record(reference) for reference in stored
        ]
        observed_identities = _typescript_reference_identities_from_anchors(anchors)
    except ValueError as exc:
        return None, str(exc)
    stored_keys = Counter(_typescript_reference_hybrid_keys(stored_identities))
    observed_keys = Counter(_typescript_reference_hybrid_keys(observed_identities))
    return observed_keys == stored_keys, None


def _ds2_links(
    ds1_ids: set[str], ds2: Mapping[str, Any]
) -> tuple[dict[str, list[str]], list[str], list[str]]:
    mapped: dict[str, list[str]] = defaultdict(list)
    unbound: list[str] = []
    errors: list[str] = []
    for entry in ds2["entries"]:
        match = V4_COUNTERPART_RE.search(entry["reason"])
        if not match:
            errors.append(f"ds2_reference_missing:{entry['id']}")
            continue
        counterpart = match.group(1)
        if counterpart == "none":
            unbound.append(entry["id"])
        elif counterpart not in ds1_ids:
            errors.append(f"ds2_reference_unresolved:{entry['id']}:{counterpart}")
        else:
            mapped[counterpart].append(entry["id"])
    return dict(mapped), unbound, errors


def _derived_operation_ids(ds1: Mapping[str, Any]) -> set[str]:
    return {
        entry["surface_id"]
        for entry in ds1["entries"]
        if entry["surface_id"].startswith("api-op-")
        and entry["readiness_state"] == "consumer_missing"
        and all(
            ref.startswith("schemas/runtime_api_v1.openapi.json:")
            for ref in entry["evidence_refs"]
        )
    }


def _derived_flag_ids(ds1: Mapping[str, Any]) -> set[str]:
    return {
        entry["surface_id"]
        for entry in ds1["entries"]
        if entry["surface_id"].startswith("flag-")
        and entry["readiness_state"] == "consumer_missing"
    }


def _iter_scan_files(scan_roots: Sequence[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for root_text in scan_roots:
        root = REPO_ROOT / root_text
        candidates = root.rglob("*") if root.is_dir() else [root]
        for path in candidates:
            if not path.is_file() or path in seen:
                continue
            if any(part in {"node_modules", ".git", "_build", "_cache"} for part in path.parts):
                continue
            seen.add(path)
            yield path


def _reference_matches(targets: Sequence[str], scan_roots: Sequence[str]) -> list[str]:
    matches: set[str] = set()
    for path in _iter_scan_files(scan_roots):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(REPO_ROOT).as_posix()
        for line_number, line in enumerate(lines, start=1):
            if any(target in line for target in targets):
                matches.add(f"{relative}:{line_number}")
    return sorted(matches)


def _typescript_import_matches(
    targets: Sequence[str],
    scan_roots: Sequence[str],
    *,
    sources: Mapping[str, str] | None = None,
) -> list[str]:
    """Return AST imports/re-exports whose module resolves or spells a target."""
    if sources is None:
        sources = {}
        for path in _iter_scan_files(scan_roots):
            if path.suffix not in {".cts", ".mts", ".ts", ".tsx"}:
                continue
            try:
                sources[path.relative_to(REPO_ROOT).as_posix()] = path.read_text(
                    encoding="utf-8"
                )
            except (UnicodeDecodeError, OSError):
                continue
    def module_stem(value: str) -> str:
        normalized = posixpath.normpath(value.replace("\\", "/"))
        return re.sub(r"\.(?:d\.)?[cm]?[jt]sx?$", "", normalized)

    target_forms: set[str] = set()
    for target in targets:
        without_suffix = module_stem(target)
        target_forms.add(without_suffix)
        dashboard_prefix = "apps/runtime-dashboard/src/"
        if without_suffix.startswith(dashboard_prefix):
            target_forms.add(without_suffix[len(dashboard_prefix) :])

    matches: set[str] = set()
    for fact in _typescript_module_facts(sources):
        if fact.get("kind") not in {"dynamic", "export", "import_declaration"}:
            continue
        module = str(fact.get("module", "")).replace("\\", "/")
        importer = str(fact.get("path", "")).replace("\\", "/")
        resolved = fact.get("resolved_module")
        candidates: set[str] = set()
        if isinstance(resolved, str) and resolved:
            candidates.add(module_stem(resolved))
        if module.startswith("@/"):
            candidates.add(
                module_stem(
                    "apps/runtime-dashboard/src/" + module.removeprefix("@/")
                )
            )
        elif module.startswith("."):
            candidates.add(
                module_stem(
                    posixpath.join(posixpath.dirname(importer), module)
                )
            )
        if candidates & target_forms:
            matches.add(f"{fact['path']}:{fact['line']}")
    return sorted(matches)


def _recompute_probe(probe: Mapping[str, Any]) -> list[str]:
    if probe["kind"] == "path_absent":
        return sorted(target for target in probe["targets"] if (REPO_ROOT / target).exists())
    if probe["kind"] == "protected_live_consumers":
        return sorted(target for target in probe["targets"] if (REPO_ROOT / target).exists())
    if probe["kind"] == "typescript_symbol_consumer_census":
        sources = _typescript_production_sources(probe["scan_roots"])
        return _ui_primitive_consumers_from_sources(sources)
    if probe["kind"] == "typescript_import_census":
        return _typescript_import_matches(probe["targets"], probe["scan_roots"])
    return _reference_matches(probe["targets"], probe["scan_roots"])


def _protected_signing_census() -> dict[str, Any]:
    targets = [
        "buildSignedPublicDecisionPacket(",
        "verifySignedPublicDecisionPacket(",
        "public/decisions/:signedId",
    ]
    observed = _reference_matches(targets, ["apps/runtime-dashboard/src", "apps/runtime-dashboard/e2e"])
    return {
        "census_id": "census-browser-signing-protected-live",
        "captured_at": REGISTER_AS_OF,
        "covers_unit_ids": ["derivation-browser-signature"],
        "ds1_evidence_ids": ["derivation-browser-signature"],
        "result": "protected_live_chain",
        "probes": [
            {
                "kind": "reference_count",
                "targets": targets,
                "scan_roots": ["apps/runtime-dashboard/src", "apps/runtime-dashboard/e2e"],
                "expected_count": len(observed),
                "observed_refs": observed,
            }
        ],
    }


def _decision_detail(
    disposition: str, consumer_slice: str, rationale: str, *, flag: bool = False
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "kind": "wire" if disposition == "wire_disposition" else "retire",
        "consumer_slice": consumer_slice,
        "rationale": rationale,
    }
    if disposition == "retire_disposition":
        detail["retirement_scope"] = (
            "frontend_exposure_registry" if flag else "frontend_adoption"
        )
        detail["revisit_condition"] = (
            "A later accepted slice names a real consumer and an authority-safe projection."
        )
    return detail


def _seed_entry(
    source: Mapping[str, Any], ds2_ids: list[str]
) -> dict[str, Any]:
    unit_id = source["surface_id"]
    entry: dict[str, Any] = {
        "unit_id": unit_id,
        "evidence_link": {
            "ds1_entry_id": unit_id,
            "ds2_adoption_ids": ds2_ids,
        },
        "disposition": "rebind_pending",
        "strangle_status": "pending",
        "owner": source["owner"],
        "owner_slice": source["owning_slice"],
        "decision_date": DECISION_DATE,
        "seed_rule": "ds1_incomplete_rebind_pending",
        "rationale": "DS1 does not record this narrow unit as implemented; its owning slice must rebind or retire it without creating a parallel owner.",
    }
    if source["readiness_state"] == "implemented":
        entry.update(
            disposition="use_as_is",
            strangle_status="not_applicable",
            seed_rule="ds1_implemented_use_as_is",
            rationale="DS1 records this narrow unit as implemented with its applicable capability links proven; no replacement owner is introduced.",
        )
    if unit_id in DELETE_ROOT_IDS:
        entry.update(
            disposition="delete_pending",
            strangle_status="pending",
            owner_slice="DS19",
            seed_rule="ds19_named_zero_consumer_candidate",
            rationale="DS1 named this false or zero-consumer substrate for DS19; deletion remains pending until a fresh live census is zero.",
        )
    if unit_id in WIRE_OPERATION_RATIONALES:
        rationale = WIRE_OPERATION_RATIONALES[unit_id]
        entry.update(
            disposition="wire_disposition",
            strangle_status="not_applicable",
            owner_slice="DS3",
            seed_rule="ds19_uncalled_openapi_wire_decision",
            rationale=rationale,
            decision_detail=_decision_detail("wire_disposition", "DS3", rationale),
        )
    if unit_id in RETIRE_OPERATION_RATIONALES:
        rationale = RETIRE_OPERATION_RATIONALES[unit_id]
        entry.update(
            disposition="retire_disposition",
            strangle_status="not_applicable",
            owner_slice="DS3",
            seed_rule="ds19_uncalled_openapi_retire_decision",
            rationale=rationale,
            decision_detail=_decision_detail("retire_disposition", "DS3", rationale),
        )
    if unit_id in FLAG_DECISIONS:
        disposition, rationale = FLAG_DECISIONS[unit_id]
        entry.update(
            disposition=disposition,
            strangle_status="not_applicable",
            owner_slice="DS5",
            seed_rule=f"ds19_consumer_missing_flag_{'wire' if disposition == 'wire_disposition' else 'retire'}_decision",
            rationale=rationale,
            decision_detail=_decision_detail(disposition, "DS5", rationale, flag=True),
        )
    if unit_id == "derivation-browser-signature":
        entry.update(
            disposition="rebind_pending",
            strangle_status="pending",
            owner_slice="DS12",
            seed_rule="protected_live_consumer_ds12_strangle",
            reference_census_id="census-browser-signing-protected-live",
            rationale="Three mounted builders, the public viewer verifier, route, and tests are live; DS12 owns the server-signing strangle and DS19 may not delete this chain.",
        )
    return entry


def _c04_rendered_contrast_source_rows(
    source_text: str | None = None,
) -> list[dict[str, str]]:
    """Return the exact seven-source C04 registry or fail closed on drift."""
    if source_text is None:
        source_text = C04_RENDERED_CONTRAST_SOURCE_PATH.read_text(encoding="utf-8")
    try:
        observed = _typescript_literal_object_array(
            source_path=C04_RENDERED_CONTRAST_SOURCE_REF,
            source=source_text,
            binding="OPAQUE_BACKGROUND_CONTRAST_SOURCES",
            owner_ast_sha256=C04_RENDERED_CONTRAST_OWNER_AST_SHA256,
        )
    except (RuntimeError, ValueError) as exc:
        raise ValueError(
            "c04_rendered_contrast_source_registry_drift:parser"
        ) from exc
    required_fields = {"sourceId", "ownerCluster", "component", "selector"}
    source_ids = [row.get("sourceId") for row in observed]
    if (
        len(observed) != 7
        or len(set(source_ids)) != 7
        or any(set(row) != required_fields for row in observed)
        or Counter(row.get("ownerCluster") for row in observed)
        != C04_RENDERED_CONTRAST_CLUSTER_COUNTS
        or any(
            row.get("selector")
            != f'[data-opaque-contrast-source="{row.get("sourceId")}"]'
            for row in observed
        )
        or _canonical_sha256(observed) != C04_RENDERED_CONTRAST_REGISTRY_SHA256
    ):
        raise ValueError("c04_rendered_contrast_source_registry_drift:identities")
    return observed


def _c04_rendered_contrast_finding(
    source_text: str | None = None,
) -> dict[str, Any]:
    """Produce the typed C04 debt without admitting the later C06 repair."""
    _c04_rendered_contrast_source_rows(source_text)
    for reference in C04_RENDERED_CONTRAST_EVIDENCE_REFS:
        if not (REPO_ROOT / reference).is_file():
            raise ValueError(
                f"c04_rendered_contrast_source_registry_drift:missing:{reference}"
            )
    return {
        "finding_id": "baseline-test-a11y-rendered-contrast-incomplete-debt",
        "finding_kind": "baseline_test_debt",
        "disposition": "rebind_pending",
        "status": "open_debt",
        "evidence_refs": list(C04_RENDERED_CONTRAST_EVIDENCE_REFS),
        "owner_slice": "DS6",
        "decision_date": "2026-08-11",
        "rationale": (
            "C01/C06/C09/C14 comprise seven declared source identities. Axe "
            "incomplete nodes are neither passes, source-attributed receipts, nor "
            "denominator members; closure requires 7/7 numeric WCAG-AA receipts "
            "on an opaque real-browser background."
        ),
    }


def _c06_rendered_contrast_finding() -> dict[str, Any]:
    """Close the exact C04 row only from the landed C16 browser release."""
    _c06_verify_c04_admission()
    receipt = _c06_c16_contrast_receipt()
    finding = _c04_rendered_contrast_finding()
    finding["status"] = "repaired"
    finding["repair_commit"] = receipt["producer_revision"]
    return finding


def _supplemental_findings() -> list[dict[str, Any]]:
    baseline_ref = "architecture/atlas_surfaces/frontend-baseline-debt-manifest.json"
    baseline = _load_json(BASELINE_PATH)
    c03_lifecycle = _c03_vitest_lifecycle_state(baseline)
    if c03_lifecycle == "invalid":
        raise ValueError("C03 supplemental source lifecycle is not admitted")
    active_test_classes = {
        row["class_id"]: row for row in baseline["vitest"]["debt_classes"]
    }
    debt_findings = [
        (
            "baseline-lint-quantity-debt",
            "baseline_lint_debt",
            f"{baseline_ref}#lint",
            None,
            "DS4",
            "The quantity diagnostic class is derived from the active lint manifest; resolved means all 75 immutable-origin identities have content-bound C06-C08 resolutions.",
        ),
        (
            "baseline-test-i18n-count-debt",
            "baseline_test_debt",
            f"{baseline_ref}#tests/i18n-count",
            "i18n-count-message-parity",
            "DS6",
            "The governed Vitest lifecycle admits exactly the three historical "
            "DS6 count-message identities while open or the C16 full-suite empty "
            "failure set when repaired.",
        ),
        (
            "baseline-test-a11y-coverage-debt",
            "baseline_test_debt",
            f"{baseline_ref}#tests/a11y-coverage",
            "shared-ui-a11y-coverage",
            "DS4",
            "The accessibility census state is derived from the active Vitest debt classes; C12 repairs the OperatorDiagnosticPanel companion without an allowlist suppression.",
        ),
        (
            "baseline-test-temporal-cursor-debt",
            "baseline_test_debt",
            f"{baseline_ref}#tests/temporal-cursor",
            "temporal-cursor-canonical-url",
            "DS4",
            "The temporal-cursor state is derived from the active Vitest debt classes; C09 closed the time-dependent identity with an injected clock.",
        ),
    ]
    findings: list[dict[str, Any]] = []
    for finding_id, kind, evidence_ref, class_id, default_owner, rationale in debt_findings:
        active_class = active_test_classes.get(class_id) if class_id else None
        if finding_id == "baseline-lint-quantity-debt":
            is_open = baseline["lint"]["error_count"] > 0
        elif finding_id == "baseline-test-i18n-count-debt":
            is_open = c03_lifecycle == "open"
        else:
            is_open = active_class is not None
        finding = {
            "finding_id": finding_id,
            "finding_kind": kind,
            "disposition": "rebind_pending",
            "status": "open_debt" if is_open else "repaired",
            "evidence_refs": [evidence_ref],
            "owner_slice": (
                active_class["owner_slice"] if active_class else default_owner
            ),
            "decision_date": DECISION_DATE,
            "rationale": rationale,
        }
        if finding_id == "baseline-test-i18n-count-debt" and not is_open:
            finding["repair_commit"] = C03_REPAIR_COMMIT
        findings.append(finding)
    findings.append(_c06_rendered_contrast_finding())
    dependencies = {
        "dependency-axe-core": "apps/runtime-dashboard/src/shared/lib/a11yAudit.ts:71",
        "dependency-intl-messageformat": "apps/runtime-dashboard/src/shared/i18n/messages/icu-messages.ts:1",
        "dependency-workbox-core": "apps/runtime-dashboard/src/sw.ts:3",
        "dependency-workbox-precaching": "apps/runtime-dashboard/src/sw.ts:4",
        "dependency-workbox-routing": "apps/runtime-dashboard/src/sw.ts:9",
        "dependency-workbox-window": "apps/runtime-dashboard/package.json#dependencies",
    }
    for finding_id, source_ref in dependencies.items():
        findings.append(
            {
                "finding_id": finding_id,
                "finding_kind": "dependency_declaration",
                "disposition": "use_as_is",
                "status": "repaired",
                "evidence_refs": [
                    source_ref,
                    "apps/runtime-dashboard/package.json#dependencies",
                    "pnpm-lock.yaml#importers/apps/runtime-dashboard",
                ],
                "owner_slice": "DS19",
                "decision_date": DECISION_DATE,
                "repair_commit": REPAIR_COMMIT,
                "rationale": "The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph.",
            }
        )
    findings.append(
        {
            "finding_id": "fixture-policy-design-case-audience",
            "finding_kind": "fixture_contract_drift",
            "disposition": "use_as_is",
            "status": "repaired",
            "evidence_refs": [
                "apps/runtime-dashboard/src/api/validators.test.ts",
                "apps/runtime-dashboard/src/api/types.ts:7050",
            ],
            "owner_slice": "DS19",
            "decision_date": DECISION_DATE,
            "repair_commit": REPAIR_COMMIT,
            "rationale": "The fixtures now type audience from the generated projection contract introduced after the fixture helper; runtime and generated code were not changed.",
        }
    )
    findings.extend(
        copy.deepcopy(descriptor)
        for _finding_id, descriptor in sorted(GOVERNED_DEBT_DESCRIPTORS.items())
    )
    findings.extend(copy.deepcopy(row) for row in _authority_presentation_rows())
    findings.extend(copy.deepcopy(row) for row in _ds11_trust_presentation_rows())
    return findings


def _validate_ds6_register_transition_findings(
    data: Mapping[str, Any],
    errors: list[str],
    expected_rows: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    """Bind each stored DS6 transition row to its canonical producer output."""
    if expected_rows is None:
        try:
            expected_rows = _supplemental_findings()
        except ValueError as exc:
            errors.append(f"ds6_register_transition_source_invalid:{exc}")
            return
    expected_by_id = {
        str(row["finding_id"]): row
        for row in expected_rows
        if row.get("finding_id") in DS6_REGISTER_TRANSITION_FINDING_IDS
    }
    stored_rows = data.get("supplemental_findings", [])
    for finding_id in sorted(DS6_REGISTER_TRANSITION_FINDING_IDS):
        matches = [
            row
            for row in stored_rows
            if isinstance(row, Mapping) and row.get("finding_id") == finding_id
        ]
        expected = expected_by_id.get(finding_id)
        if len(matches) != 1 or expected is None or matches[0] != expected:
            errors.append(f"ds6_register_transition_drift:{finding_id}")


def _json_container_end(text: str, start: int) -> int:
    """Return the inclusive end of one JSON array/object without reformatting."""
    opener = text[start]
    if opener not in "[{":
        raise ValueError(f"JSON container expected at offset {start}")
    closer = "]" if opener == "[" else "}"
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == opener:
            depth += 1
        elif character == closer:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"unterminated JSON container at offset {start}")


def _c03_resolved_baseline_manifest_text(text: str) -> str:
    """Surgically produce the C03 Vitest transition without reserializing peers."""
    candidate = _c03_resolved_baseline_manifest(json.loads(text))
    match = re.search(r'^  "vitest":\s*({)', text, re.MULTILINE)
    if match is None:
        raise ValueError("vitest object missing")
    start = match.start(1)
    end = _json_container_end(text, start)
    rendered_lines = json.dumps(
        candidate["vitest"], indent=2, ensure_ascii=False
    ).splitlines()
    replacement = rendered_lines[0] + "\n" + "\n".join(
        "  " + line for line in rendered_lines[1:]
    )
    return text[:start] + replacement + text[end + 1 :]


def _supplemental_section_spans(
    text: str,
) -> tuple[int, int, list[tuple[str, int, int]]]:
    match = re.search(r'^  "supplemental_findings":\s*(\[)', text, re.MULTILINE)
    if match is None:
        raise ValueError("supplemental_findings array missing")
    start = match.start(1)
    end = _json_container_end(text, start)
    objects: list[tuple[str, int, int]] = []
    index = start + 1
    while index < end:
        while index < end and (text[index].isspace() or text[index] == ","):
            index += 1
        if index >= end:
            break
        if text[index] != "{":
            raise ValueError(
                f"supplemental finding object expected at offset {index}"
            )
        object_end = _json_container_end(text, index)
        row = json.loads(text[index : object_end + 1])
        finding_id = row.get("finding_id")
        if not isinstance(finding_id, str):
            raise ValueError("supplemental finding_id missing")
        objects.append((finding_id, index, object_end))
        index = object_end + 1
    return start, end, objects


def _supplemental_section(
    text: str,
) -> tuple[int, int, list[tuple[str, str]]]:
    """Expose byte slices used by preservation and idempotence tests."""
    start, end, spans = _supplemental_section_spans(text)
    return (
        start,
        end,
        [
            (finding_id, text[object_start : object_end + 1])
            for finding_id, object_start, object_end in spans
        ],
    )


def _surgical_supplemental_finding_ids(text: str) -> set[str]:
    """Return descriptor rows and retired generated rows owned by refresh."""
    descriptor_ids = set(GOVERNED_DEBT_DESCRIPTORS) | set(
        AUTHORITY_PRESENTATION_DEBT_SPECS
    ) | DS6_REGISTER_TRANSITION_FINDING_IDS
    _start, _end, spans = _supplemental_section_spans(text)
    for finding_id, object_start, object_end in spans:
        row = json.loads(text[object_start : object_end + 1])
        if row.get("finding_kind") in {
            "producer_binding_debt",
            "authority_presentation_debt",
        } and (
            finding_id not in descriptor_ids
            and finding_id not in DS11_TRUST_PRESENTATION_FINDING_IDS
        ):
            descriptor_ids.add(finding_id)
    return descriptor_ids


def _remove_supplemental_finding_text(text: str, finding_id: str) -> str:
    """Remove one refresh-owned supplemental object without rewriting neighbors."""
    _start, _end, spans = _supplemental_section_spans(text)
    for index, (candidate_id, object_start, object_end) in enumerate(spans):
        if candidate_id != finding_id:
            continue
        if index + 1 < len(spans):
            next_start = spans[index + 1][1]
            return text[:object_start] + text[next_start:]
        if index:
            previous_end = spans[index - 1][2]
            return text[: previous_end + 1] + text[object_end + 1 :]
        return text[:object_start] + text[object_end + 1 :]
    return text


def _render_supplemental_finding(row: Mapping[str, Any]) -> str:
    rendered = json.dumps(row, indent=2, ensure_ascii=False)
    lines = rendered.splitlines()
    return lines[0] + "\n" + "\n".join("    " + line for line in lines[1:])


def _c06_rendered_contrast_transition_text(text: str) -> str:
    """Transition only the exact C04 row, or admit the exact repaired result."""
    _start, _end, spans = _supplemental_section_spans(text)
    matches = [
        (object_start, object_end)
        for finding_id, object_start, object_end in spans
        if finding_id == C06_RENDERED_CONTRAST_FINDING_ID
    ]
    if len(matches) != 1:
        raise ValueError(
            "C06 rendered contrast transition rejected:target cardinality"
        )
    object_start, object_end = matches[0]
    stored = json.loads(text[object_start : object_end + 1])
    admitted_open = _c04_rendered_contrast_finding()
    admitted_repaired = _c06_rendered_contrast_finding()
    if stored == admitted_repaired:
        return text
    if stored != admitted_open:
        raise ValueError(
            "C06 rendered contrast transition rejected:predecessor:"
            + _canonical_sha256(stored)
        )

    candidate = (
        text[:object_start]
        + _render_supplemental_finding(admitted_repaired)
        + text[object_end + 1 :]
    )
    _candidate_start, _candidate_end, candidate_rows = _supplemental_section(
        candidate
    )
    _original_start, _original_end, original_rows = _supplemental_section(text)
    original_peers = [
        row for row in original_rows if row[0] != C06_RENDERED_CONTRAST_FINDING_ID
    ]
    candidate_peers = [
        row for row in candidate_rows if row[0] != C06_RENDERED_CONTRAST_FINDING_ID
    ]
    if original_peers != candidate_peers:
        raise ValueError("C06 rendered contrast transition rejected:peer drift")
    return candidate


def _ds11_trust_presentation_preservation_errors(
    original_text: str, candidate_text: str
) -> list[str]:
    """Prove the DS11 writer changed only its two target JSON objects."""
    try:
        original_start, original_end, original_rows = _supplemental_section(
            original_text
        )
        candidate_start, candidate_end, candidate_rows = _supplemental_section(
            candidate_text
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return [f"ds11_trust_presentation_preservation_span_invalid:{exc}"]
    if original_text[: original_start + 1] != candidate_text[: candidate_start + 1]:
        return ["ds11_trust_presentation_prefix_drift"]
    if original_text[original_end:] != candidate_text[candidate_end:]:
        return ["ds11_trust_presentation_suffix_drift"]
    original_peers = [
        row
        for row in original_rows
        if row[0] not in DS11_TRUST_PRESENTATION_FINDING_IDS
    ]
    candidate_peers = [
        row
        for row in candidate_rows
        if row[0] not in DS11_TRUST_PRESENTATION_FINDING_IDS
    ]
    if original_peers != candidate_peers:
        return ["ds11_trust_presentation_peer_drift"]
    return []


def _ds11_trust_presentation_transition_text(
    text: str,
    *,
    scan: Mapping[str, Any] | None = None,
) -> str:
    """Transition exactly two known DS11 predecessors, or admit their repair."""
    expected_rows = {
        str(row["finding_id"]): row
        for row in _ds11_trust_presentation_rows(scan)
    }
    if set(expected_rows) != DS11_TRUST_PRESENTATION_FINDING_IDS:
        raise ValueError("DS11 C04 transition generated denominator drift")
    _start, _end, spans = _supplemental_section_spans(text)
    target_spans = [
        (finding_id, object_start, object_end)
        for finding_id, object_start, object_end in spans
        if finding_id in DS11_TRUST_PRESENTATION_FINDING_IDS
    ]
    if (
        len(target_spans) != len(DS11_TRUST_PRESENTATION_FINDING_IDS)
        or {finding_id for finding_id, _start, _end in target_spans}
        != DS11_TRUST_PRESENTATION_FINDING_IDS
    ):
        raise ValueError("DS11 C04 transition rejected:target cardinality")
    stored = {
        finding_id: json.loads(text[object_start : object_end + 1])
        for finding_id, object_start, object_end in target_spans
    }
    if all(
        stored[finding_id] == expected_rows[finding_id]
        for finding_id in DS11_TRUST_PRESENTATION_FINDING_IDS
    ):
        return text
    review_predecessors: dict[str, dict[str, Any]] = {}
    for finding_id, expected in expected_rows.items():
        predecessor = copy.deepcopy(expected)
        bound_refs = [
            ref
            for ref in predecessor["evidence_refs"]
            if ref.startswith(DS11_TRUST_GLYPHS_PATH + "#content-sha256=")
        ]
        if len(bound_refs) != 1:
            raise ValueError("DS11 C04 transition generated issuer receipt drift")
        predecessor["evidence_refs"] = [
            DS11_TRUST_GLYPHS_PATH if ref == bound_refs[0] else ref
            for ref in predecessor["evidence_refs"]
        ]
        review_predecessors[finding_id] = predecessor
    is_review_predecessor = all(
        stored[finding_id] == review_predecessors[finding_id]
        for finding_id in DS11_TRUST_PRESENTATION_FINDING_IDS
    )
    if not is_review_predecessor and any(
        _canonical_sha256(stored[finding_id])
        != DS11_C04_OPENING_ROW_SHA256[finding_id]
        for finding_id in DS11_TRUST_PRESENTATION_FINDING_IDS
    ):
        raise ValueError("DS11 C04 transition rejected:predecessor restamp")
    candidate = text
    for finding_id, object_start, object_end in sorted(
        target_spans, key=lambda item: item[1], reverse=True
    ):
        candidate = (
            candidate[:object_start]
            + _render_supplemental_finding(expected_rows[finding_id])
            + candidate[object_end + 1 :]
        )
    preservation_errors = _ds11_trust_presentation_preservation_errors(
        text, candidate
    )
    if preservation_errors:
        raise ValueError(
            "DS11 C04 transition rejected:" + ";".join(preservation_errors)
        )
    return candidate


def _ds11_trust_presentation_report_row_span(
    text: str, finding_id: str
) -> tuple[int, int, str]:
    """Locate one rendered finding row without reserializing report peers."""
    matches = list(
        re.finditer(
            r"^\| `" + re.escape(finding_id) + r"` \|.*\|$",
            text,
            re.MULTILINE,
        )
    )
    if len(matches) != 1:
        raise ValueError(
            "DS11 C04 report transition rejected:target cardinality:" + finding_id
        )
    match = matches[0]
    return match.start(), match.end(), match.group(0)


def _ds11_trust_presentation_report_transition_text(
    text: str,
    *,
    opening_register_text: str,
    candidate_register_text: str,
) -> str:
    """Rewrite only the two C04 report rows and preserve every other byte."""
    opening_report = render_report(json.loads(opening_register_text))
    candidate_report = render_report(json.loads(candidate_register_text))
    replacements: list[tuple[int, int, str]] = []
    already_repaired = True
    for finding_id in sorted(DS11_TRUST_PRESENTATION_FINDING_IDS):
        start, end, stored = _ds11_trust_presentation_report_row_span(text, finding_id)
        _opening_start, _opening_end, opening = _ds11_trust_presentation_report_row_span(
            opening_report, finding_id
        )
        _candidate_start, _candidate_end, repaired = (
            _ds11_trust_presentation_report_row_span(candidate_report, finding_id)
        )
        if stored == repaired:
            continue
        already_repaired = False
        if stored != opening:
            raise ValueError(
                "DS11 C04 report transition rejected:predecessor restamp:"
                + finding_id
            )
        replacements.append((start, end, repaired))
    if already_repaired:
        return text
    candidate = text
    for start, end, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:start] + replacement + candidate[end:]

    original_spans = [
        _ds11_trust_presentation_report_row_span(text, finding_id)
        for finding_id in sorted(DS11_TRUST_PRESENTATION_FINDING_IDS)
    ]
    candidate_spans = [
        _ds11_trust_presentation_report_row_span(candidate, finding_id)
        for finding_id in sorted(DS11_TRUST_PRESENTATION_FINDING_IDS)
    ]

    def gaps(
        source: str, spans: Sequence[tuple[int, int, str]]
    ) -> list[str]:
        result: list[str] = []
        previous = 0
        for start, end, _row in spans:
            result.append(source[previous:start])
            previous = end
        result.append(source[previous:])
        return result

    if gaps(text, original_spans) != gaps(candidate, candidate_spans):
        raise ValueError("DS11 C04 report transition rejected:peer drift")
    return candidate


def _refresh_supplemental_findings_text(text: str) -> str:
    """Upsert descriptor rows while preserving every other register byte."""
    descriptor_ids = (
        set(GOVERNED_DEBT_DESCRIPTORS)
        | set(AUTHORITY_PRESENTATION_DEBT_SPECS)
        | DS6_REGISTER_TRANSITION_FINDING_IDS
    )
    generated = {
        row["finding_id"]: row
        for row in _supplemental_findings()
        if row["finding_id"] in descriptor_ids
    }
    ds11_generated = {
        row["finding_id"]: row
        for row in _supplemental_findings()
        if row["finding_id"] in DS11_TRUST_PRESENTATION_FINDING_IDS
    }
    _start, _end, stored_spans = _supplemental_section_spans(text)
    stored_ds11 = {
        finding_id: json.loads(text[object_start : object_end + 1])
        for finding_id, object_start, object_end in stored_spans
        if finding_id in DS11_TRUST_PRESENTATION_FINDING_IDS
    }
    if set(stored_ds11) != DS11_TRUST_PRESENTATION_FINDING_IDS or any(
        stored_ds11[finding_id] != ds11_generated.get(finding_id)
        for finding_id in DS11_TRUST_PRESENTATION_FINDING_IDS
    ):
        raise ValueError(
            "trust presentation requires the dedicated DS11 C04 transition"
        )
    refresh_owned_ids = _surgical_supplemental_finding_ids(text)
    refreshed = text
    for finding_id in sorted(refresh_owned_ids - descriptor_ids):
        refreshed = _remove_supplemental_finding_text(refreshed, finding_id)

    _start, _end, spans = _supplemental_section_spans(refreshed)
    seen: set[str] = set()
    for finding_id, object_start, object_end in reversed(spans):
        if finding_id not in generated:
            continue
        if finding_id == C06_RENDERED_CONTRAST_FINDING_ID:
            stored = json.loads(refreshed[object_start : object_end + 1])
            if stored != generated[finding_id]:
                raise ValueError(
                    "rendered contrast requires the dedicated C06 transition"
                )
            seen.add(finding_id)
            continue
        if finding_id in AUTHORITY_PRESENTATION_DEBT_SPECS:
            stored = json.loads(refreshed[object_start : object_end + 1])
            if _authority_row_semantic_value(stored) == _authority_row_semantic_value(
                generated[finding_id]
            ):
                seen.add(finding_id)
                continue
        replacement = _render_supplemental_finding(generated[finding_id])
        refreshed = (
            refreshed[:object_start]
            + replacement
            + refreshed[object_end + 1 :]
        )
        seen.add(finding_id)

    missing = sorted(descriptor_ids - seen)
    if C06_RENDERED_CONTRAST_FINDING_ID in missing:
        raise ValueError("rendered contrast requires the dedicated C06 transition")
    if not missing:
        return refreshed
    start, end, refreshed_spans = _supplemental_section_spans(refreshed)
    if refreshed_spans:
        insertion_at = refreshed_spans[-1][2] + 1
        insertion = "".join(
            ",\n    " + _render_supplemental_finding(generated[finding_id])
            for finding_id in missing
        )
    else:
        insertion_at = start + 1
        insertion = "\n" + "\n".join(
            "    " + _render_supplemental_finding(generated[finding_id])
            for finding_id in missing
        ) + "\n  "
    if insertion_at > end:
        raise ValueError("supplemental insertion escaped its array")
    return refreshed[:insertion_at] + insertion + refreshed[insertion_at:]


def _raw_transport_writer_preservation_errors(
    original_text: str, candidate_text: str
) -> list[str]:
    """Return byte-preservation failures for the surgical supplemental writer."""
    original_start, original_end, original_rows = _supplemental_section(original_text)
    candidate_start, candidate_end, candidate_rows = _supplemental_section(candidate_text)
    errors: list[str] = []
    if original_text[: original_start + 1] != candidate_text[: candidate_start + 1]:
        errors.append("raw_transport_writer_prefix_drift")
    if original_text[original_end:] != candidate_text[candidate_end:]:
        errors.append("raw_transport_writer_suffix_drift")
    descriptor_ids = _surgical_supplemental_finding_ids(original_text)
    original_accepted = [
        text for finding_id, text in original_rows if finding_id not in descriptor_ids
    ]
    candidate_descriptor_ids = _surgical_supplemental_finding_ids(candidate_text)
    candidate_accepted = [
        text
        for finding_id, text in candidate_rows
        if finding_id not in candidate_descriptor_ids
    ]
    if original_accepted != candidate_accepted:
        errors.append("raw_transport_writer_accepted_row_drift")
    return errors


def _ds15_acquisition_routes_preservation_errors(
    original_text: str, candidate_text: str
) -> list[str]:
    """Allow only the query root and refresh-owned supplemental rows to move."""
    try:
        query_candidate = _ds15_query_memory_transition_text(original_text)
        original_start, original_end, _original = _json_entry_object_span(
            original_text, C11B_QUERY_MEMORY_ROOT_ID
        )
        candidate_start, candidate_end, _candidate = _json_entry_object_span(
            query_candidate, C11B_QUERY_MEMORY_ROOT_ID
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return [f"ds15_acquisition_routes_preservation_span_invalid:{exc}"]

    errors: list[str] = []
    if original_text[:original_start] != query_candidate[:candidate_start]:
        errors.append("ds15_acquisition_routes_query_prefix_drift")
    if original_text[original_end:] != query_candidate[candidate_end:]:
        errors.append("ds15_acquisition_routes_query_suffix_drift")
    errors.extend(
        _raw_transport_writer_preservation_errors(query_candidate, candidate_text)
    )
    try:
        expected = _refresh_supplemental_findings_text(query_candidate)
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(f"ds15_acquisition_routes_refresh_invalid:{exc}")
    else:
        if candidate_text != expected:
            errors.append("ds15_acquisition_routes_candidate_payload_drift")
    return errors


def _ds15_acquisition_routes_candidate_errors(
    data: Mapping[str, Any],
    *,
    report_parity: bool,
) -> list[str]:
    """Permit only the independently admitted C13 source drift in DS15's family."""
    errors = validate_register(
        data,
        live_probes=False,
        report_parity=report_parity,
    )
    admitted, admission_errors = _ds10_c13_external_nonclosure_admission(
        errors,
        expected_mismatches=DS15_C13_EXTERNAL_SOURCE_BINDING_MISMATCHES,
    )
    return [
        *admission_errors,
        *_ds10_blocking_register_errors(
            errors,
            admitted_external_errors=admitted,
        ),
    ]


def _ds15_acquisition_routes_candidate_text(
    original_text: str,
    *,
    verify_idempotency: bool = True,
) -> str:
    """Build the bounded DS15 query/disposition transition without peer drift."""
    query_candidate = _ds15_query_memory_transition_text(original_text)
    candidate = _refresh_supplemental_findings_text(query_candidate)
    preservation_errors = _ds15_acquisition_routes_preservation_errors(
        original_text, candidate
    )
    if preservation_errors:
        raise ValueError(
            "DS15 acquisition-routes candidate rejected:"
            + ";".join(preservation_errors)
        )
    candidate_errors = _ds15_acquisition_routes_candidate_errors(
        json.loads(candidate),
        report_parity=False,
    )
    if candidate_errors:
        raise ValueError(
            "DS15 acquisition-routes candidate rejected:"
            + ";".join(candidate_errors)
        )
    if verify_idempotency:
        repeated = _ds15_acquisition_routes_candidate_text(
            candidate,
            verify_idempotency=False,
        )
        if repeated != candidate:
            raise ValueError("DS15 acquisition-routes candidate is not idempotent")
    return candidate


def _write_ds15_acquisition_routes_family() -> dict[str, int]:
    """Atomically write DS15's register/report while preserving DS1 bytes."""
    original_texts = {
        REGISTER_PATH: REGISTER_PATH.read_text(encoding="utf-8"),
        REPORT_PATH: REPORT_PATH.read_text(encoding="utf-8"),
    }
    original_readiness = DS1_PATH.read_bytes()
    register_candidate = _ds15_acquisition_routes_candidate_text(
        original_texts[REGISTER_PATH]
    )
    register_data = json.loads(register_candidate)
    report_candidate = render_report(register_data)
    candidates = {
        REGISTER_PATH: register_candidate,
        REPORT_PATH: report_candidate,
    }

    def validate_after() -> list[str]:
        errors: list[str] = []
        for governed_path, expected_text in candidates.items():
            if governed_path.read_text(encoding="utf-8") != expected_text:
                errors.append(
                    "ds15_acquisition_routes_family_readback_drift:"
                    + str(governed_path)
                )
        errors.extend(
            _ds15_acquisition_routes_candidate_errors(
                _load_json(REGISTER_PATH),
                report_parity=True,
            )
        )
        if DS1_PATH.read_bytes() != original_readiness:
            errors.append("ds15_acquisition_routes_readiness_ledger_drift")
        return errors

    def final_pre_promote_fence() -> None:
        for governed_path, original_text in original_texts.items():
            if governed_path.read_text(encoding="utf-8") != original_text:
                raise ValueError(
                    "DS15 acquisition-routes governed preimage moved:"
                    + str(governed_path)
                )
        if DS1_PATH.read_bytes() != original_readiness:
            raise ValueError("DS15 acquisition-routes readiness preimage moved")

    _failure_atomic_write_texts(
        candidates,
        validate_after=validate_after,
        pre_promote=final_pre_promote_fence,
    )
    return {
        "badge_sites": len(DS15_ADDED_AUTHORITY_BADGE_CLASSIFICATIONS),
        "query_consumer_refs": len(DS15_QUERY_MEMORY_SUCCESSOR_REFS),
        "readiness_entries_preserved": len(json.loads(original_readiness)["entries"]),
    }


def _seeded_negatives() -> list[dict[str, Any]]:
    affected = {
        "DS1-N001": ["derivation-browser-signature"],
        "DS1-N015": ["feature-whatif::legacy-local-whatif-subgraph"],
        "DS1-N017": sorted(FLAG_DECISIONS),
        "DS1-N019": [
            "worker-data-transform",
            "worker-dag-layout",
            "worker-json-parse",
        ],
        "DS1-N021": sorted(COLLABORATION_IDS),
    }
    return [
        {
            "negative_id": negative_id,
            "source_ref": f"docs/reference/frontend/atlas-live-application-audit.md:{812 + index}",
            "lifecycle": "still_required",
            "affected_unit_ids": affected.get(negative_id, []),
            "may_count_as_passing_test": False,
            "rationale": "DS19 preserves the seeded negative until an executable deletion makes its original substrate wholly or partially obsolete.",
        }
        for index, negative_id in enumerate(
            [f"DS1-N{number:03d}" for number in range(1, 24)], start=1
        )
    ]


def build_seed_register() -> dict[str, Any]:
    """Build the DS19 seed while preserving explicit storage adjudications."""
    ds1 = _load_json(DS1_PATH)
    ds2 = _load_json(DS2_PATH)
    if not REGISTER_PATH.exists():
        raise ValueError("storage_construction_census_missing")
    storage_census = _load_json(REGISTER_PATH).get("storage_construction_census")
    if not isinstance(storage_census, Mapping):
        raise ValueError("storage_construction_census_missing")
    ds1_ids = {entry["surface_id"] for entry in ds1["entries"]}
    mapped, unbound, mapping_errors = _ds2_links(ds1_ids, ds2)
    if mapping_errors:
        raise ValueError(";".join(mapping_errors))
    entries = [
        _seed_entry(entry, mapped.get(entry["surface_id"], []))
        for entry in ds1["entries"]
    ]
    return {
        "$schema": "./frontend-disposition-register.schema.json",
        "schema_version": "1.2",
        "register_id": "atlas-ds19-frontend-disposition",
        "as_of": REGISTER_AS_OF,
        "controlled_vocabulary_source": "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md",
        "authority": {
            "authoritative_for": [
                "frontend estate disposition",
                "frontend strangle status and successor ownership",
                "fresh deletion-census receipts",
            ],
            "may_not_use_for": [
                "upgrading DS1 readiness or maturity",
                "rewriting DS2 adoption verdicts",
                "claiming a pending rebind or retirement is implemented",
                "deleting server endpoints from a frontend-only decision",
            ],
        },
        "sources": {
            "ds1": {
                "path": "architecture/atlas_surfaces/live-application-readiness-ledger.json",
                "ledger_id": ds1["ledger_id"],
                "sha256": _sha256(DS1_PATH),
                "expected_entries": len(ds1["entries"]),
            },
            "ds2": {
                "path": "architecture/atlas_surfaces/atlas-v15-adoption-ledger.json",
                "ledger_id": ds2["ledger_id"],
                "sha256": _sha256(DS2_PATH),
                "expected_entries": len(ds2["entries"]),
            },
            "ds0": {
                "path": "docs/brand/ATLAS_SOURCE_OF_TRUTH.md",
                "decision_id": "D4",
                "decision_date": "2026-07-16",
            },
        },
        "seed_policy": {
            "rules": [
                "Preserve DS1 order and identity: one root row per DS1 surface_id.",
                "Map DS1 implemented to use_as_is; map every other unoverridden root to rebind_pending.",
                "Apply DS19 deletion and wire-or-retire overrides only to mechanically derived source sets.",
                "Link every DS2 row exactly once as mapped evidence or an explicitly unbound adoption ID.",
            ],
            "ds1_root_count": 261,
            "ds2_mapped_count": sum(len(ids) for ids in mapped.values()),
            "ds2_unbound_count": len(unbound),
        },
        "baseline_debt_manifest_ref": "architecture/atlas_surfaces/frontend-baseline-debt-manifest.json",
        "ds2_unbound_adoption_ids": unbound,
        "reference_censuses": [_protected_signing_census()],
        "storage_construction_census": copy.deepcopy(storage_census),
        "entries": entries,
        "subunits": [
            {
                "unit_id": "feature-whatif::legacy-local-whatif-subgraph",
                "parent_ds1_entry_id": "feature-whatif",
                "scope_kind": "dead_subgraph",
                "scope_refs": CLUSTER_PROOFS["whatif-local"]["paths"],
                "disposition": "delete_pending",
                "strangle_status": "pending",
                "owner": "team-design",
                "owner_slice": "DS19",
                "decision_date": DECISION_DATE,
                "rationale": "Only the unreachable local parameter/store branch is a deletion candidate; the server-backed ScenarioWorkbench remains live.",
            },
            {
                "unit_id": "route-app-layout::ru-ui-catalog",
                "parent_ds1_entry_id": "route-app-layout",
                "scope_kind": "legacy_continuity",
                "scope_refs": ["apps/runtime-dashboard/src/shared/i18n/locales/ru.json"],
                "disposition": "frozen_legacy_continuity",
                "strangle_status": "not_applicable",
                "continuity_guard": {
                    "required_path": "apps/runtime-dashboard/src/shared/i18n/locales/ru.json",
                    "forbidden_claims": [
                        "Russian is an active selectable UI locale.",
                        "The frozen catalog is a DS19 deletion target.",
                    ],
                    "separate_capability": "Read-only Russian source-content rendering is separate from UI locale exposure.",
                },
                "owner": "team-design",
                "owner_slice": "DS0",
                "decision_date": "2026-07-16",
                "rationale": "Ratified D4 freezes the legacy ru UI catalog in place: not used, not deleted, and not an active-locale claim.",
            },
        ],
        "supplemental_findings": _supplemental_findings(),
        "ds8_strangle_coverage": build_ds8_strangle_coverage(
            baseline_commit=DS8_STRANGLE_BASE_COMMIT,
            source_commit=DS8_STRANGLE_SOURCE_COMMIT,
        ),
        "ds8b_post_freeze_transition": build_ds8b_post_freeze_transition(
            baseline_commit=DS8B_TRANSITION_BASE_COMMIT,
            source_commit=DS8B_TRANSITION_SOURCE_COMMIT,
            historical_coverage=build_ds8_strangle_coverage(
                baseline_commit=DS8_STRANGLE_BASE_COMMIT,
                source_commit=DS8_STRANGLE_SOURCE_COMMIT,
            ),
        ),
        "seeded_negative_lifecycle": _seeded_negatives(),
    }


def _schema_errors(data: Mapping[str, Any], schema_path: Path) -> list[str]:
    schema = _load_json(schema_path)
    if schema_path == SCHEMA_PATH:
        # The committed schema references Phase A's single owning-slice
        # vocabulary.  Resolve that local reference explicitly so validation
        # cannot fall back to a network retrieval or a machine-specific URI.
        readiness_schema = _load_json(ATLAS_DIR / "surface-readiness-ledger.schema.json")
        schema = copy.deepcopy(schema)
        schema["$defs"]["ownerSlice"] = readiness_schema["$defs"]["owningSlice"]

        def bind_local_reference(value: Any) -> None:
            if isinstance(value, dict):
                if value.get("$ref") == "surface-readiness-ledger.schema.json#/$defs/owningSlice":
                    value["$ref"] = "#/$defs/ownerSlice"
                for child in value.values():
                    bind_local_reference(child)
            elif isinstance(value, list):
                for child in value:
                    bind_local_reference(child)

        bind_local_reference(schema)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    return [
        "schema:" + "/".join(str(part) for part in error.absolute_path) + ":" + error.message
        for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
    ]


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _c03_required_match(
    pattern: str,
    text: str,
    label: str,
    *,
    flags: int = 0,
) -> re.Match[str]:
    match = re.search(pattern, text, flags)
    if match is None:
        raise ValueError(f"C16 receipt source field missing: {label}")
    return match


def _c03_c16_receipt_from_sources(
    plan_text: str,
    journal_text: str,
) -> dict[str, Any]:
    """Recompute the C16 compact receipt from its landed, content-bound sources."""
    source_texts = {
        "docs/plans/active/atlas-slices/DS6-evidence-workflow.md": plan_text,
        "docs/plans/active/atlas-slices/DS6-evidence-workflow-journal.md": (
            journal_text
        ),
    }
    for source_ref, expected_sha256 in C03_RECEIPT_SOURCE_SHA256.items():
        actual_sha256 = hashlib.sha256(
            source_texts[source_ref].encode("utf-8")
        ).hexdigest()
        if actual_sha256 != expected_sha256:
            raise ValueError(
                f"C16 receipt source hash drift:{source_ref}:{actual_sha256}"
            )

    command = _c03_required_match(
        r"`command=([^`]+)`",
        plan_text,
        "command",
        flags=re.DOTALL,
    ).group(1)
    command = re.sub(r"\s+", " ", command).strip()
    wall_duration = float(
        _c03_required_match(
            r"`wall_duration_seconds=([0-9.]+)`",
            plan_text,
            "wall_duration_seconds",
        ).group(1)
    )
    vitest_duration = float(
        _c03_required_match(
            r"`vitest_duration_seconds=([0-9.]+)`",
            plan_text,
            "vitest_duration_seconds",
        ).group(1)
    )
    exit_code = int(
        _c03_required_match(
            r"`exit_code=(\d+)`",
            plan_text,
            "exit_code",
        ).group(1)
    )
    plan_files = tuple(
        int(value)
        for value in _c03_required_match(
            r"`test_files=\{total:(\d+),passed:(\d+),failed:(\d+)\}`",
            plan_text,
            "test_files",
        ).groups()
    )
    plan_tests = tuple(
        int(value)
        for value in _c03_required_match(
            r"`tests=\{total:(\d+),passed:(\d+),failed:(\d+)\}`",
            plan_text,
            "tests",
        ).groups()
    )
    failure_sha256 = _c03_required_match(
        r"`failure_set\.sha256=([a-f0-9]{64})`",
        plan_text,
        "failure_set.sha256",
    ).group(1)
    plan_raw_sha256 = _c03_required_match(
        r"The raw JSON receipt SHA-256 is\s+`([a-f0-9]{64})`",
        plan_text,
        "raw receipt SHA-256",
    ).group(1)

    table = _c03_required_match(
        r"\| whole-suite Vitest JSON \| 1,200 \| GREEN \| ([0-9.]+) "
        r"\| [^|]+ \| (\d+)/(\d+) files; (\d+)/(\d+) tests; "
        r"(\d+) failed/pending/skipped/todo \|",
        journal_text,
        "serialized whole-suite table row",
    )
    journal_wall = float(table.group(1))
    journal_files = (int(table.group(2)), int(table.group(3)), 0)
    journal_tests = (int(table.group(4)), int(table.group(5)), 0)
    journal_nonpass = int(table.group(6))
    receipt_detail = _c03_required_match(
        r"Vitest duration is\s+([0-9.]+) s; raw JSON is ([\d,]+) bytes "
        r"with SHA-256\s+`([a-f0-9]{64})`",
        journal_text,
        "serialized whole-suite receipt detail",
        flags=re.DOTALL,
    )
    journal_vitest_duration = float(receipt_detail.group(1))
    raw_receipt_bytes = int(receipt_detail.group(2).replace(",", ""))
    journal_raw_sha256 = receipt_detail.group(3)
    delta_detail = _c03_required_match(
        r"above entry HEAD `([a-f0-9]{40})`; that binary diff has SHA-256\s+"
        r"`([a-f0-9]{64})`",
        journal_text,
        "C16 entry and source delta",
        flags=re.DOTALL,
    )
    entry_revision, source_delta_sha256 = delta_detail.groups()

    if (
        exit_code != 0
        or plan_files != journal_files
        or plan_tests != journal_tests
        or journal_nonpass != 0
        or wall_duration != journal_wall
        or vitest_duration != journal_vitest_duration
        or plan_raw_sha256 != journal_raw_sha256
        or failure_sha256 != _canonical_sha256([])
    ):
        raise ValueError("C16 receipt sources do not reconcile")

    return {
        "disposition": "resolved",
        "command": command,
        "wall_duration_seconds": wall_duration,
        "vitest_duration_seconds": vitest_duration,
        "exit_code": exit_code,
        "test_files": {
            "total": plan_files[0],
            "passed": plan_files[1],
            "failed": plan_files[2],
        },
        "tests": {
            "total": plan_tests[0],
            "passed": plan_tests[1],
            "failed": plan_tests[2],
        },
        "failure_set": {
            "hash_algorithm": "sha256",
            "serialization": "RFC8785_JCS",
            "payload": "flat_sorted_failures",
            "sort_key": [
                "test_file",
                "test_name",
                "assertion_line",
                "assertion_anchor",
            ],
            "sha256": failure_sha256,
        },
        "debt_classes": [],
        "receipt_provenance": {
            "receipt_kind": "whole_suite_vitest_json",
            "producer_revision": C03_REPAIR_COMMIT,
            "entry_revision": entry_revision,
            "source_delta_sha256": source_delta_sha256,
            "raw_receipt_sha256": plan_raw_sha256,
            "raw_receipt_bytes": raw_receipt_bytes,
            "predicate_provenance": "recomputed",
            "authority_purpose": "c16_landed_whole_suite_release",
            "raw_receipt_availability": "not_persisted_in_repository",
            "source_refs": [
                {
                    "path": source_ref,
                    "content_sha256": source_sha256,
                }
                for source_ref, source_sha256 in C03_RECEIPT_SOURCE_SHA256.items()
            ],
        },
}


def _c03_git_text(*arguments: str) -> str:
    """Run one fixed-argument Git query and return text or fail closed."""
    completed = subprocess.run(  # noqa: S603 - fixed caller-owned argument vectors
        [  # noqa: S607 - repository tool resolved by the controlled environment
            "git",
            *arguments,
        ],
        cwd=REPO_ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            "C16 Git provenance query failed: " + completed.stderr.strip()
        )
    return completed.stdout


@contextmanager
def _ds11_trust_presentation_register_lock() -> Iterable[None]:
    """Serialize the C04 register/report family on a worktree-local Git lock."""
    lock_ref = _c03_git_text(
        "rev-parse",
        "--git-path",
        "ds11-trust-presentation-register.lock",
    ).strip()
    lock_path = Path(lock_ref)
    if not lock_path.is_absolute():
        lock_path = REPO_ROOT.parent / lock_path
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("DS11 C04 register-family lock is held") from exc
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _c03_git_bytes(*arguments: str) -> bytes:
    """Run one fixed-argument Git query and return bytes or fail closed."""
    completed = subprocess.run(  # noqa: S603 - fixed caller-owned argument vectors
        [  # noqa: S607 - repository tool resolved by the controlled environment
            "git",
            *arguments,
        ],
        cwd=REPO_ROOT.parent,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            "C16 Git provenance query failed: "
            + completed.stderr.decode("utf-8", errors="replace").strip()
        )
    return completed.stdout


def _c03_verify_c16_git_provenance(
    provenance: Mapping[str, object],
) -> None:
    """Recompute the C16 entry revision and complete five-path source delta."""
    parent_line = _c03_git_text(
        "rev-list",
        "--parents",
        "-n",
        "1",
        C03_REPAIR_COMMIT,
    ).strip()
    revision_parts = parent_line.split()
    if (
        len(revision_parts) != 2
        or revision_parts[0] != C03_REPAIR_COMMIT
        or revision_parts[1] != provenance.get("entry_revision")
    ):
        raise ValueError("C16 entry revision drift")

    changed_paths = set(
        _c03_git_text(
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            C03_REPAIR_COMMIT,
        ).splitlines()
    )
    receipt_source_paths = {
        f"policy-engine/{source_ref}"
        for source_ref in C03_RECEIPT_SOURCE_SHA256
    }
    mechanism_paths = sorted(changed_paths - receipt_source_paths)
    if (
        not receipt_source_paths <= changed_paths
        or len(changed_paths) != 7
        or len(mechanism_paths) != 5
        or any(
            not source_path.startswith("policy-engine/apps/runtime-dashboard/")
            for source_path in mechanism_paths
        )
    ):
        raise ValueError("C16 complete source-delta denominator drift")
    source_delta = _c03_git_bytes(
        "diff",
        "--binary",
        str(provenance["entry_revision"]),
        C03_REPAIR_COMMIT,
        "--",
        *mechanism_paths,
    )
    actual_sha256 = hashlib.sha256(source_delta).hexdigest()
    if actual_sha256 != provenance.get("source_delta_sha256"):
        raise ValueError(f"C16 source-delta hash drift:{actual_sha256}")


@lru_cache(maxsize=1)
def _c03_c16_receipt() -> dict[str, Any]:
    """Resolve the landed C16 receipt sources without trusting current prose."""
    _c03_git_text(
        "merge-base",
        "--is-ancestor",
        C03_REPAIR_COMMIT,
        "HEAD",
    )
    source_texts: dict[str, str] = {}
    for source_ref in C03_RECEIPT_SOURCE_SHA256:
        source_texts[source_ref] = _c03_git_text(
            "show",
            f"{C03_REPAIR_COMMIT}:policy-engine/{source_ref}",
        )
    receipt = _c03_c16_receipt_from_sources(
        source_texts["docs/plans/active/atlas-slices/DS6-evidence-workflow.md"],
        source_texts[
            "docs/plans/active/atlas-slices/DS6-evidence-workflow-journal.md"
        ],
    )
    _c03_verify_c16_git_provenance(receipt["receipt_provenance"])
    return receipt


def _c06_c16_contrast_receipt_from_sources(
    plan_text: str,
    journal_text: str,
) -> dict[str, Any]:
    """Resolve the final accepted contrast receipt from the immutable C16 release."""
    try:
        release = _c03_c16_receipt_from_sources(plan_text, journal_text)
        plan_receipt = _c03_required_match(
            r"The C16 receipt is exactly (\d+)/(\d+): one Storybook story "
            r"passed in ([0-9.]+) s, its raw\s+JSON SHA-256 is\s+"
            r"`([a-f0-9]{64})`,\s+and all seven numeric source receipts "
            r"were admitted atomically\.",
            plan_text,
            "final opaque Storybook plan receipt",
            flags=re.DOTALL,
        )
        journal_receipt = _c03_required_match(
            r"the final bounded run completed GREEN at exact (\d+)/(\d+) "
            r"in ([0-9.]+) s\. Its one\s+Storybook file/test passed, raw JSON "
            r"is ([\d,]+) bytes, and SHA-256 is\s+`([a-f0-9]{64})`",
            journal_text,
            "final opaque Storybook journal receipt",
            flags=re.DOTALL,
        )
        table_receipt = _c03_required_match(
            r"\| opaque Storybook probe \| (\d+) \| GREEN \| ([0-9.]+) "
            r"\| [^|\n]+ \| exact (\d+)/(\d+) atomic computed-pass "
            r"receipts; zero violations/incompletes in the seven custom "
            r"source observations \|",
            journal_text,
            "serialized opaque Storybook table row",
        )
        meta_report = _c03_required_match(
            r"The raw Storybook automatic a11y meta-report separately retains "
            r"three\s+unattributed incomplete nodes, including one "
            r"`color-contrast` incomplete for\s+the exact excluded `aria-hidden` "
            r"`⊙` glyph\. They are outside the seven custom\s+source observations "
            r"and are neither attributed source receipts nor silently\s+counted "
            r"green; the custom story's atomic result remains exact (\d+)/(\d+)\.",
            journal_text,
            "automatic Storybook a11y meta-report scope",
            flags=re.DOTALL,
        )
        predicate_sha256 = _c03_required_match(
            r"`hasOpaqueBackground`, the classifier, and the frozen registry "
            r"remain\s+byte-identical; the predicate SHA-256 is\s+"
            r"`([a-f0-9]{64})`",
            journal_text,
            "opaque Storybook predicate hash",
            flags=re.DOTALL,
        ).group(1)
    except ValueError as exc:
        raise ValueError("C16 contrast receipt source invalid") from exc

    plan_total, plan_passed = (int(value) for value in plan_receipt.groups()[:2])
    plan_wall = float(plan_receipt.group(3))
    plan_raw_sha256 = plan_receipt.group(4)
    journal_total, journal_passed = (
        int(value) for value in journal_receipt.groups()[:2]
    )
    journal_wall = float(journal_receipt.group(3))
    raw_receipt_bytes = int(journal_receipt.group(4).replace(",", ""))
    journal_raw_sha256 = journal_receipt.group(5)
    ceiling = int(table_receipt.group(1))
    table_wall = float(table_receipt.group(2))
    table_total = int(table_receipt.group(3))
    table_passed = int(table_receipt.group(4))
    meta_custom_total = int(meta_report.group(1))
    meta_custom_passed = int(meta_report.group(2))
    provenance = release["receipt_provenance"]
    if (
        (plan_total, plan_passed) != (7, 7)
        or (journal_total, journal_passed) != (7, 7)
        or (table_total, table_passed) != (7, 7)
        or (meta_custom_total, meta_custom_passed) != (7, 7)
        or plan_wall != 14.02
        or journal_wall != plan_wall
        or table_wall != plan_wall
        or ceiling != 300
        or raw_receipt_bytes != 163_320
        or plan_raw_sha256 != C06_CONTRAST_RAW_RECEIPT_SHA256
        or journal_raw_sha256 != plan_raw_sha256
        or predicate_sha256
        != C06_CONTRAST_EVIDENCE_SHA256[C04_RENDERED_CONTRAST_SOURCE_REF]
        or provenance.get("producer_revision") != C03_REPAIR_COMMIT
        or provenance.get("entry_revision") != C06_C16_ENTRY_REVISION
        or provenance.get("source_delta_sha256")
        != C06_C16_SOURCE_DELTA_SHA256
    ):
        raise ValueError("C16 contrast receipt sources do not reconcile")

    return {
        "receipt_kind": "landed_opaque_storybook_release",
        "producer_revision": C03_REPAIR_COMMIT,
        "entry_revision": C06_C16_ENTRY_REVISION,
        "source_delta_sha256": C06_C16_SOURCE_DELTA_SHA256,
        "wall_duration_seconds": plan_wall,
        "story_files": {"total": 1, "passed": 1, "failed": 0},
        "tests": {"total": 1, "passed": 1, "failed": 0},
        "custom_source_observations": {
            "sources": {"total": plan_total, "passed": plan_passed, "failed": 0},
            "violation_count": 0,
            "incomplete_count": 0,
            "numeric_source_receipts": True,
            "atomic": True,
        },
        "automatic_a11y_meta_report": {
            "incomplete_count": 3,
            "color_contrast_incomplete_count": 1,
            "source_attribution": "unattributed",
            "denominator_membership": "outside_custom_source_observations",
        },
        "raw_receipt": {
            "format": "storybook_json",
            "bytes": raw_receipt_bytes,
            "sha256": plan_raw_sha256,
            "availability": "not_persisted_in_repository",
        },
        "source_registry_sha256": C04_RENDERED_CONTRAST_REGISTRY_SHA256,
        "owner_ast_sha256": C04_RENDERED_CONTRAST_OWNER_AST_SHA256,
        "release_provenance": "recomputed",
        "measurement_provenance": "task_authoritative_landed_release",
        "authority_purpose": "c16_landed_opaque_storybook_release",
        "source_refs": [
            {
                "path": source_ref,
                "content_sha256": source_sha256,
            }
            for source_ref, source_sha256 in C03_RECEIPT_SOURCE_SHA256.items()
        ],
    }


def _c06_verify_c04_admission() -> None:
    """Require the landed C04 commit and its exact open predecessor row."""
    try:
        _c03_git_text(
            "merge-base",
            "--is-ancestor",
            C06_C04_ADMISSION_COMMIT,
            "HEAD",
        )
    except ValueError as exc:
        raise ValueError("C04 admission ancestry missing") from exc

    register_ref = REGISTER_PATH.relative_to(REPO_ROOT).as_posix()
    try:
        admission_text = _c03_git_text(
            "show",
            f"{C06_C04_ADMISSION_COMMIT}:policy-engine/{register_ref}",
        )
        _start, _end, rows = _supplemental_section(admission_text)
        matches = [
            serialized
            for finding_id, serialized in rows
            if finding_id == C06_RENDERED_CONTRAST_FINDING_ID
        ]
        if len(matches) != 1:
            raise ValueError("target cardinality")
        admitted_row = json.loads(matches[0])
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("C04 admission source invalid") from exc
    if admitted_row != _c04_rendered_contrast_finding():
        raise ValueError("C04 admission predecessor row drift")


def _c06_verify_c16_contrast_evidence(
    current_evidence_bytes: Mapping[str, bytes] | None = None,
) -> None:
    """Bind current C04 evidence inputs to the exact landed C16 Git objects."""
    _c03_c16_receipt()
    expected_refs = set(C04_RENDERED_CONTRAST_EVIDENCE_REFS)
    if current_evidence_bytes is None:
        current_evidence_bytes = {
            source_ref: (REPO_ROOT / source_ref).read_bytes()
            for source_ref in C04_RENDERED_CONTRAST_EVIDENCE_REFS
        }
    if set(current_evidence_bytes) != expected_refs:
        raise ValueError("C16 contrast current evidence drift:population")

    changed_paths = set(
        _c03_git_text(
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            C03_REPAIR_COMMIT,
        ).splitlines()
    )
    story_ref = C04_RENDERED_CONTRAST_EVIDENCE_REFS[2]
    changed_evidence_refs = {
        source_ref
        for source_ref in expected_refs
        if f"policy-engine/{source_ref}" in changed_paths
    }
    if changed_evidence_refs != {story_ref}:
        raise ValueError("C16 contrast historical evidence drift:changed paths")

    historical: dict[str, bytes] = {}
    for source_ref, expected_sha256 in C06_CONTRAST_EVIDENCE_SHA256.items():
        source_bytes = _c03_git_bytes(
            "show",
            f"{C03_REPAIR_COMMIT}:policy-engine/{source_ref}",
        )
        historical[source_ref] = source_bytes
        if hashlib.sha256(source_bytes).hexdigest() != expected_sha256:
            raise ValueError(
                f"C16 contrast historical evidence drift:{source_ref}"
            )
        current_bytes = current_evidence_bytes.get(source_ref, b"")
        if (
            hashlib.sha256(current_bytes).hexdigest()
            != C06_CONTRAST_CURRENT_EVIDENCE_SHA256[source_ref]
        ):
            raise ValueError(f"C16 contrast current evidence drift:{source_ref}")

    current_delta_refs = {
        source_ref
        for source_ref in expected_refs
        if current_evidence_bytes[source_ref] != historical[source_ref]
    }
    if current_delta_refs != {story_ref}:
        raise ValueError("C16 contrast current evidence drift:declared delta")

    for unchanged_ref in C04_RENDERED_CONTRAST_EVIDENCE_REFS[:2]:
        parent_bytes = _c03_git_bytes(
            "show",
            f"{C06_C16_ENTRY_REVISION}:policy-engine/{unchanged_ref}",
        )
        if parent_bytes != historical[unchanged_ref]:
            raise ValueError(
                f"C16 contrast historical evidence drift:{unchanged_ref}:parent"
            )
    parent_story = _c03_git_bytes(
        "show",
        f"{C06_C16_ENTRY_REVISION}:policy-engine/{story_ref}",
    )
    if parent_story == historical[story_ref]:
        raise ValueError("C16 contrast historical evidence drift:story unchanged")

    try:
        _c04_rendered_contrast_source_rows(
            historical[C04_RENDERED_CONTRAST_SOURCE_REF].decode("utf-8")
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("C16 contrast historical registry drift") from exc


@lru_cache(maxsize=1)
def _c06_c16_contrast_receipt() -> dict[str, Any]:
    """Return the Git-bound, task-authoritative C16 contrast release receipt."""
    _c03_c16_receipt()
    source_texts = {
        source_ref: _c03_git_text(
            "show",
            f"{C03_REPAIR_COMMIT}:policy-engine/{source_ref}",
        )
        for source_ref in C03_RECEIPT_SOURCE_SHA256
    }
    receipt = _c06_c16_contrast_receipt_from_sources(
        source_texts["docs/plans/active/atlas-slices/DS6-evidence-workflow.md"],
        source_texts[
            "docs/plans/active/atlas-slices/DS6-evidence-workflow-journal.md"
        ],
    )
    _c06_verify_c16_contrast_evidence()
    return receipt


def _expected_resolution_content_roles(
    resolutions: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], frozenset[str]]:
    """Derive every cluster/path role set from the resolution graph."""
    roles_by_cluster_path: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for resolution in resolutions:
        cluster_id = resolution["cluster_id"]
        for field, role in RESOLUTION_REFERENCE_ROLES:
            value = resolution[field]
            references = value if isinstance(value, list) else [value]
            for reference in references:
                roles_by_cluster_path[(cluster_id, reference)].add(role)
    return {
        key: frozenset(roles)
        for key, roles in roles_by_cluster_path.items()
    }


@lru_cache(maxsize=32)
def _chart_quantity_scalar_semantics_hold(
    chart_source: bytes,
    quantity_format_source: bytes,
) -> bool:
    """Execute the authored scalar adapter with representative set-valued inputs."""
    dashboard_root = REPO_ROOT / "apps/runtime-dashboard"
    runner = r"""
const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");
const dashboardRoot = process.argv[1];
const requireFromDashboard = createRequire(path.join(dashboardRoot, "package.json"));
const ts = requireFromDashboard("typescript");
const input = JSON.parse(fs.readFileSync(0, "utf8"));

function authoredFunction(source, name) {
  const sourceFile = ts.createSourceFile(
    `${name}.ts`,
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  let found = null;
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name?.text === name) {
      found = node.getText(sourceFile).replace(/^export\s+/u, "");
      return;
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  if (found === null) throw new Error(`missing authored function: ${name}`);
  return found;
}

const authored = [
  authoredFunction(input.quantityFormatSource, "finitePoint"),
  authoredFunction(input.chartSource, "chartQuantityMembers"),
  authoredFunction(input.chartSource, "chartQuantityScalarPoint"),
  "module.exports = { chartQuantityScalarPoint };",
].join("\n");
const javascript = ts.transpileModule(authored, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const evaluated = { exports: {} };
new Function("module", "exports", javascript)(evaluated, evaluated.exports);
const scalar = evaluated.exports.chartQuantityScalarPoint;
const quantity = (point) => ({ point });
const holds =
  scalar(null) === null &&
  scalar(quantity(0.5)) === 0.5 &&
  scalar(quantity(Number.NaN)) === null &&
  scalar([quantity(1), quantity(2)]) === null &&
  scalar([quantity(-0.25)]) === -0.25;
process.exit(holds ? 0 : 1);
"""
    completed = subprocess.run(
        ["node", "-e", runner, str(dashboard_root)],
        cwd=REPO_ROOT,
        input=json.dumps(
            {
                "chartSource": chart_source.decode("utf-8"),
                "quantityFormatSource": quantity_format_source.decode("utf-8"),
            }
        ),
        capture_output=True,
        check=False,
        text=True,
    )
    return completed.returncode == 0


def _resolution_content_binding_errors(
    lint: Mapping[str, Any],
    *,
    source_bytes_override: Mapping[str, bytes] | None = None,
) -> list[str]:
    """Require an exact role projection and bind every referenced file's bytes."""
    errors: list[str] = []
    expected = _expected_resolution_content_roles(lint["resolutions"])
    bindings = lint["resolution_content_bindings"]
    stored_by_key: defaultdict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(
        list
    )
    for binding in bindings:
        stored_by_key[(binding["cluster_id"], binding["path"])].append(binding)

    expected_keys = set(expected)
    stored_keys = set(stored_by_key)
    for cluster_id, path in sorted(expected_keys - stored_keys):
        errors.append(f"lint_resolution_content_binding_missing:{cluster_id}:{path}")
    for cluster_id, path in sorted(stored_keys - expected_keys):
        errors.append(f"lint_resolution_content_binding_extra:{cluster_id}:{path}")
    for cluster_id, path in sorted(stored_keys):
        rows = stored_by_key[(cluster_id, path)]
        if len(rows) != 1:
            errors.append(f"lint_resolution_content_binding_duplicate:{cluster_id}:{path}")
        expected_roles = expected.get((cluster_id, path))
        for binding in rows:
            if expected_roles is not None and frozenset(binding["roles"]) != expected_roles:
                errors.append(
                    f"lint_resolution_content_binding_role_drift:{cluster_id}:{path}"
                )
            if source_bytes_override is not None and path in source_bytes_override:
                source_bytes = source_bytes_override[path]
            else:
                source_path = REPO_ROOT / path
                try:
                    source_bytes = source_path.read_bytes()
                except OSError:
                    errors.append(
                        f"lint_resolution_content_binding_path_missing:{cluster_id}:{path}"
                    )
                    continue
            if hashlib.sha256(source_bytes).hexdigest() != binding["sha256"]:
                errors.append(f"lint_resolution_content_hash_drift:{cluster_id}:{path}")
            if (
                cluster_id == "C07"
                and path
                == "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.tsx"
            ):
                quantity_format_source = (
                    REPO_ROOT
                    / "apps/runtime-dashboard/src/shared/ui/quantity/quantity-format.ts"
                ).read_bytes()
                if not _chart_quantity_scalar_semantics_hold(
                    source_bytes, quantity_format_source
                ):
                    errors.append(f"lint_c07_scalar_semantic_probe_failed:{path}")
    return errors


def _lint_identity_rows(
    lint: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Return stable IDs and enriched identities for the active lint rows."""
    rows: list[dict[str, Any]] = []
    for file_entry in lint["files"]:
        for diagnostic in file_entry["diagnostics"]:
            identity = {
                "path": file_entry["path"],
                "source_content_sha256": file_entry["content_sha256"],
                **diagnostic,
            }
            rows.append(identity)
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))
    return [(_canonical_sha256(row), row) for row in rows]


def _architecture_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    """Discard presentation text while retaining the exact architecture edge."""
    return {field: row.get(field) for field in ARCHITECTURE_IDENTITY_FIELDS}


def _architecture_identity_rows(
    architecture: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    rows = [_architecture_identity(row) for row in architecture["violations"]]
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))
    return [(_canonical_sha256(row), row) for row in rows]


def _resolution_partition_errors(
    *,
    label: str,
    active_rows: Sequence[tuple[str, Mapping[str, Any]]],
    resolutions: Sequence[Mapping[str, Any]],
    origin_count: int,
    origin_identity_sha256: str,
    identity_from_resolution: Any,
) -> list[str]:
    """Prove active and resolved rows are one disjoint immutable-origin partition."""
    errors: list[str] = []
    active_ids = [identity_id for identity_id, _row in active_rows]
    stored_resolution_ids = [row["origin_identity_sha256"] for row in resolutions]
    if len(set(active_ids)) != len(active_ids):
        errors.append(f"{label}_active_identity_duplicate")
    if len(set(stored_resolution_ids)) != len(stored_resolution_ids):
        errors.append(f"{label}_resolution_identity_duplicate")
    if set(active_ids) & set(stored_resolution_ids):
        errors.append(f"{label}_partition_overlap")

    resolved_rows: list[Mapping[str, Any]] = []
    for resolution in resolutions:
        identity = identity_from_resolution(resolution["origin_identity"])
        identity_id = _canonical_sha256(identity)
        if identity_id != resolution["origin_identity_sha256"]:
            errors.append(
                f"{label}_resolution_identity_hash_drift:"
                f"{resolution['origin_identity_sha256']}"
            )
        resolved_rows.append(identity)

    union_rows = [row for _identity_id, row in active_rows] + resolved_rows
    if len(union_rows) < origin_count:
        errors.append(f"{label}_partition_missing_identity")
    elif len(union_rows) > origin_count:
        errors.append(f"{label}_partition_extra_identity")
    union_rows = sorted(
        union_rows,
        key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")),
    )
    if _canonical_sha256(union_rows) != origin_identity_sha256:
        errors.append(f"{label}_origin_identity_set_hash_drift")
    return errors


def _flatten_lint_diagnostics(baseline: Mapping[str, Any]) -> list[dict[str, Any]]:
    sort_key = baseline["lint"]["diagnostic_set"]["sort_key"]
    return sorted(
        [
            diagnostic
            for file_entry in baseline["lint"]["files"]
            for diagnostic in file_entry["diagnostics"]
        ],
        key=lambda item: tuple(item.get(key) for key in sort_key),
    )


def _flatten_vitest_failures(baseline: Mapping[str, Any]) -> list[dict[str, Any]]:
    sort_key = baseline["vitest"]["failure_set"]["sort_key"]
    return sorted(
        [
            failure
            for debt_class in baseline["vitest"]["debt_classes"]
            for failure in debt_class["failures"]
        ],
        key=lambda item: tuple(item.get(key) for key in sort_key),
    )


def _c03_vitest_lifecycle_state(baseline: Mapping[str, Any]) -> str:
    """Classify only the two content-bound C03 lifecycle states."""
    vitest = baseline.get("vitest")
    if not isinstance(vitest, Mapping):
        return "invalid"
    receipt_sha256 = _canonical_sha256(vitest)
    if receipt_sha256 == C03_OPEN_VITEST_SHA256:
        return "open"
    if receipt_sha256 != C03_RESOLVED_VITEST_SHA256:
        return "invalid"
    expected_receipt = _c03_c16_receipt()
    if any(vitest.get(field) != value for field, value in expected_receipt.items()):
        return "invalid"
    return "resolved"


def _c03_resolved_baseline_manifest(
    baseline: Mapping[str, Any],
) -> dict[str, Any]:
    """Produce the exact C16-resolved Vitest state from the admitted C03 pair."""
    vitest = baseline.get("vitest")
    if not isinstance(vitest, Mapping):
        raise ValueError("C03 Vitest receipt is missing")
    lifecycle = _c03_vitest_lifecycle_state(baseline)
    if lifecycle == "resolved":
        return copy.deepcopy(dict(baseline))
    if lifecycle != "open":
        receipt_sha256 = _canonical_sha256(vitest)
        raise ValueError(f"C03 Vitest receipt is not admitted: {receipt_sha256}")

    candidate = copy.deepcopy(dict(baseline))
    candidate["vitest"].update(copy.deepcopy(_c03_c16_receipt()))
    resolved_sha256 = _canonical_sha256(candidate["vitest"])
    if resolved_sha256 != C03_RESOLVED_VITEST_SHA256:
        raise ValueError(f"C03 resolved Vitest receipt drifted: {resolved_sha256}")
    return candidate


def validate_baseline_manifest(
    baseline: Mapping[str, Any],
    *,
    verify_source_bytes: bool = False,
    source_bytes_override: Mapping[str, bytes] | None = None,
) -> list[str]:
    """Validate immutable origins, active debt, resolutions, and provenance."""
    errors = _schema_errors(baseline, BASELINE_SCHEMA_PATH)
    if errors:
        return errors

    lint = baseline["lint"]
    diagnostics = _flatten_lint_diagnostics(baseline)
    if len(diagnostics) != lint["error_count"]:
        errors.append("lint_active_error_count_drift")
    if lint["warning_count"] != 0:
        errors.append("lint_active_warning_count_drift")
    if len(lint["files"]) != lint["source_file_count"]:
        errors.append("lint_active_file_count_drift")
    if _canonical_sha256(diagnostics) != lint["diagnostic_set"]["sha256"]:
        errors.append("lint_active_payload_hash_drift")
    active_lint_rows = _lint_identity_rows(lint)
    if _canonical_sha256([row for _identity_id, row in active_lint_rows]) != lint[
        "identity_set_sha256"
    ]:
        errors.append("lint_active_identity_set_hash_drift")
    for file_entry in lint["files"]:
        if file_entry["diagnostic_count"] != len(file_entry["diagnostics"]):
            errors.append(f"lint_file_count_drift:{file_entry['path']}")
        actual_rule_counts = Counter(
            diagnostic["rule_id"] for diagnostic in file_entry["diagnostics"]
        )
        stored_rule_counts = {
            row["rule_id"]: row["count"] for row in file_entry["rule_counts"]
        }
        if dict(actual_rule_counts) != stored_rule_counts:
            errors.append(f"lint_file_rule_count_drift:{file_entry['path']}")
        if any(
            diagnostic["path"] != file_entry["path"]
            or diagnostic["rule_id"] != "policyos/quantity-must-be-wrapped"
            or diagnostic["severity"] != 2
            for diagnostic in file_entry["diagnostics"]
        ):
            errors.append(f"lint_diagnostic_identity_invalid:{file_entry['path']}")
        if verify_source_bytes:
            path = REPO_ROOT / file_entry["path"]
            if not path.exists():
                errors.append(f"lint_active_source_missing:{file_entry['path']}")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != file_entry["content_sha256"]:
                errors.append(f"lint_active_source_hash_drift:{file_entry['path']}")

    origin = lint["immutable_origin"]
    if (
        origin["error_count"] != LINT_ORIGIN_COUNT
        or origin["source_file_count"] != LINT_ORIGIN_FILE_COUNT
        or origin["diagnostic_set"]["sha256"] != LINT_ORIGIN_DIAGNOSTIC_SHA256
        or origin["identity_set_sha256"] != LINT_ORIGIN_IDENTITY_SHA256
        or origin["raw_receipt_sha256"] != LINT_ORIGIN_RAW_RECEIPT_SHA256
        or origin["rule_identity"]["implementation_sha256"]
        != LINT_ORIGIN_RULE_SHA256
        or origin["rule_identity"]["configuration_sha256"]
        != LINT_ORIGIN_CONFIG_SHA256
    ):
        errors.append("lint_immutable_origin_anchor_drift")
    errors.extend(
        _resolution_partition_errors(
            label="lint",
            active_rows=active_lint_rows,
            resolutions=lint["resolutions"],
            origin_count=LINT_ORIGIN_COUNT,
            origin_identity_sha256=LINT_ORIGIN_IDENTITY_SHA256,
            identity_from_resolution=lambda row: dict(row),
        )
    )
    errors.extend(
        _resolution_content_binding_errors(
            lint,
            source_bytes_override=source_bytes_override,
        )
    )
    c06_classifications = Counter(
        row["classification"]
        for row in lint["resolutions"]
        if row["cluster_id"] == "C06"
    )
    if c06_classifications != {
        "quantity_enveloped": 8,
        "authority_guess_removed": 9,
        "collection_control": 2,
        "parser_control": 1,
    }:
        errors.append("lint_c06_resolution_classification_drift")
    c07_classifications = Counter(
        row["classification"]
        for row in lint["resolutions"]
        if row["cluster_id"] == "C07"
    )
    if c07_classifications != {
        "quantity_semantics": 4,
        "layout_geometry": 33,
    }:
        errors.append("lint_c07_resolution_classification_drift")
    c08_classifications = Counter(
        row["classification"] for row in lint["resolutions"] if row["cluster_id"] == "C08"
    )
    if c08_classifications != {
        "interaction_control": 3,
        "layout_geometry": 5,
        "motion_geometry": 9,
        "operational_request_control": 1,
    }:
        errors.append("lint_c08_resolution_classification_drift")
    for resolution in lint["resolutions"]:
        identity_id = resolution["origin_identity_sha256"]
        if resolution["cluster_id"] == "C06" and resolution["semantic_kind"] == "decision_bearing":
            expected_closure = (
                "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.test.ts"
                if resolution["classification"] == "authority_guess_removed"
                and resolution["origin_identity"]["path"]
                == "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts"
                else "apps/runtime-dashboard/src/shared/ui/quantity/quantityDecisionProducers.test.tsx"
            )
            if resolution["closure_test_ref"] != expected_closure:
                errors.append(f"lint_c06_semantic_closure_drift:{identity_id}")
        if resolution["cluster_id"] == "C07":
            expected_semantic_kind = (
                "decision_bearing"
                if resolution["classification"] == "quantity_semantics"
                else "non_authority_control"
            )
            if resolution["semantic_kind"] != expected_semantic_kind:
                errors.append("lint_c07_semantic_kind_drift")
            if (
                resolution["closure_test_ref"]
                != "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.test.tsx"
            ):
                errors.append(f"lint_c07_semantic_closure_drift:{identity_id}")
            if (
                resolution["classification"] == "quantity_semantics"
                and "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.tsx"
                not in resolution["implementation_refs"]
            ):
                errors.append(f"lint_c07_semantic_adapter_drift:{identity_id}")
        if resolution["cluster_id"] == "C08":
            if resolution["semantic_kind"] != "non_authority_control":
                errors.append("lint_c08_semantic_kind_drift")
            if (
                resolution["closure_test_ref"]
                != "apps/runtime-dashboard/eslint-plugin-local/rules/quantity-must-be-wrapped.test.cjs"
            ):
                errors.append(f"lint_c08_semantic_closure_drift:{identity_id}")
            if (
                "apps/runtime-dashboard/src/shared/lib/domain/nonAuthorityNumeric.ts"
                not in resolution["implementation_refs"]
            ):
                errors.append(f"lint_c08_semantic_adapter_drift:{identity_id}")
            if (
                "apps/runtime-dashboard/eslint-plugin-local/rules/quantity-must-be-wrapped.cjs"
                not in resolution["implementation_refs"]
            ):
                errors.append(f"lint_c08_rule_binding_drift:{identity_id}")
        references = [
            *resolution["implementation_refs"],
            *resolution["consumer_refs"],
            resolution["closure_test_ref"],
        ]
        for reference in references:
            issue = _reference_resolution_error(reference)
            if issue:
                errors.append(f"lint_resolution_{issue}:{identity_id}")

    rule = lint["rule_identity"]
    for path_key, hash_key in (
        ("implementation_path", "implementation_sha256"),
        ("configuration_path", "configuration_sha256"),
    ):
        path = REPO_ROOT / rule[path_key]
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != rule[hash_key]:
            errors.append(f"lint_rule_input_hash_drift:{rule[path_key]}")

    architecture = baseline["architecture"]
    architecture_rows = _architecture_identity_rows(architecture)
    if len(architecture_rows) != architecture["violation_count"]:
        errors.append("architecture_active_violation_count_drift")
    if len({row["source_path"] for row in architecture["violations"]}) != architecture[
        "source_file_count"
    ]:
        errors.append("architecture_active_file_count_drift")
    if _canonical_sha256([row for _identity_id, row in architecture_rows]) != architecture[
        "identity_set_sha256"
    ]:
        errors.append("architecture_active_identity_set_hash_drift")
    architecture_origin = architecture["immutable_origin"]
    if (
        architecture_origin["violation_count"] != ARCHITECTURE_ORIGIN_COUNT
        or architecture_origin["source_file_count"] != ARCHITECTURE_ORIGIN_FILE_COUNT
        or architecture_origin["identity_set_sha256"]
        != ARCHITECTURE_ORIGIN_IDENTITY_SHA256
        or architecture_origin["producer_sha256"]
        != ARCHITECTURE_ORIGIN_PRODUCER_SHA256
    ):
        errors.append("architecture_immutable_origin_anchor_drift")
    errors.extend(
        _resolution_partition_errors(
            label="architecture",
            active_rows=architecture_rows,
            resolutions=architecture["resolutions"],
            origin_count=ARCHITECTURE_ORIGIN_COUNT,
            origin_identity_sha256=ARCHITECTURE_ORIGIN_IDENTITY_SHA256,
            identity_from_resolution=_architecture_identity,
        )
    )
    producer_path = REPO_ROOT / architecture["producer_path"]
    if (
        not producer_path.exists()
        or hashlib.sha256(producer_path.read_bytes()).hexdigest()
        != architecture["producer_sha256"]
    ):
        errors.append("architecture_producer_hash_drift")
    for resolution in architecture["resolutions"]:
        identity_id = resolution["origin_identity_sha256"]
        references = [
            *resolution["implementation_refs"],
            *resolution["consumer_refs"],
            resolution["closure_test_ref"],
        ]
        for reference in references:
            issue = _reference_resolution_error(reference)
            if issue:
                errors.append(f"architecture_resolution_{issue}:{identity_id}")
    c18_resolutions = [
        resolution
        for resolution in architecture["resolutions"]
        if resolution["cluster_id"] == "C18"
    ]
    if len(c18_resolutions) != 1:
        errors.append("architecture_c18_resolution_count_drift")
    elif c18_resolutions[0]["classification"] != "feature_public_barrel":
        errors.append("architecture_c18_resolution_classification_drift")
    for resolution in architecture["resolutions"]:
        if (
            resolution["cluster_id"] != "C18"
            and resolution["classification"] != "shared_dependency_inverted"
        ):
            errors.append(
                "architecture_non_c18_resolution_classification_drift:"
                f"{resolution['origin_identity_sha256']}"
            )
    if verify_source_bytes:
        for row in architecture["violations"]:
            path = REPO_ROOT / row["source_path"]
            if not path.exists():
                errors.append(f"architecture_active_source_missing:{row['source_path']}")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != row[
                "source_content_sha256"
            ]:
                errors.append(f"architecture_active_source_hash_drift:{row['source_path']}")

    receipt_sha256 = _canonical_sha256(baseline["vitest"])
    try:
        c03_lifecycle = _c03_vitest_lifecycle_state(baseline)
    except ValueError as exc:
        errors.append(f"vitest_c16_receipt_source_invalid:{exc}")
    else:
        if c03_lifecycle == "invalid":
            errors.append(f"vitest_lifecycle_receipt_drift:{receipt_sha256}")
    if baseline["vitest"]["parent_reproduction"]["matches_full_run_failure_set"] is not True:
        errors.append("vitest_parent_reproduction_missing")
    return errors


def _normalise_eslint_path(path_text: str) -> str:
    path = Path(path_text)
    if not path.is_absolute():
        path = (REPO_ROOT / "apps/runtime-dashboard" / path).resolve()
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError as exc:
        raise ValueError(f"eslint result outside repository: {path_text}") from exc


def compare_lint_results(
    baseline: Mapping[str, Any], raw_results_path: Path
) -> list[str]:
    """Require the current ESLint diagnostic multiset to be a baseline subset."""
    raw = json.loads(raw_results_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "results" in raw:
        raw = raw["results"]
    if not isinstance(raw, list):
        return ["lint_results_shape_invalid"]
    baseline_files = {entry["path"]: entry for entry in baseline["lint"]["files"]}
    baseline_counter: Counter[tuple[Any, ...]] = Counter()
    for file_entry in baseline["lint"]["files"]:
        for diagnostic in file_entry["diagnostics"]:
            baseline_counter[
                (
                    file_entry["path"],
                    file_entry["content_sha256"],
                    diagnostic["rule_id"],
                    diagnostic["severity"],
                    diagnostic["line"],
                    diagnostic["column"],
                    diagnostic.get("end_line"),
                    diagnostic.get("end_column"),
                    diagnostic.get("message_id"),
                    diagnostic["message"],
                )
            ] += 1
    current_counter: Counter[tuple[Any, ...]] = Counter()
    errors: list[str] = []
    for result in raw:
        relative = _normalise_eslint_path(result["filePath"])
        source = REPO_ROOT / relative
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else "missing"
        for suppressed in result.get("suppressedMessages", []):
            if suppressed.get("ruleId") == "policyos/quantity-must-be-wrapped":
                errors.append(f"quantity_rule_new_suppression:{relative}:{suppressed.get('line')}")
        for message in result.get("messages", []):
            if message.get("severity", 0) == 0:
                continue
            identity = (
                relative,
                source_hash,
                message.get("ruleId"),
                message.get("severity"),
                message.get("line"),
                message.get("column"),
                message.get("endLine"),
                message.get("endColumn"),
                message.get("messageId"),
                message.get("message"),
            )
            current_counter[identity] += 1
    for identity, count in current_counter.items():
        if count > baseline_counter[identity]:
            errors.append(
                "lint_new_diagnostic:"
                + str(identity[0])
                + ":"
                + str(identity[2])
                + ":"
                + str(identity[4])
            )
    for identity, count in baseline_counter.items():
        if count > current_counter[identity]:
            errors.append(
                "lint_expected_diagnostic_missing:"
                + str(identity[0])
                + ":"
                + str(identity[2])
                + ":"
                + str(identity[4])
            )
    return errors


def compare_architecture_results(
    baseline: Mapping[str, Any], raw_results_path: Path
) -> list[str]:
    """Require the live custom architecture stage to equal the active set."""
    raw = json.loads(raw_results_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("violations"), list):
        return ["architecture_results_shape_invalid"]
    expected = Counter(
        identity_id
        for identity_id, _row in _architecture_identity_rows(baseline["architecture"])
    )
    current = Counter(
        _canonical_sha256(_architecture_identity(row)) for row in raw["violations"]
    )
    errors: list[str] = []
    for identity_id, count in current.items():
        if count > expected[identity_id]:
            errors.append(f"architecture_new_violation:{identity_id}")
    for identity_id, count in expected.items():
        if count > current[identity_id]:
            errors.append(f"architecture_expected_violation_missing:{identity_id}")
    return errors


def _normalise_vitest_path(path_text: str) -> str:
    path = Path(path_text)
    if path.is_absolute():
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    if path_text.startswith("apps/runtime-dashboard/"):
        return path_text
    return f"apps/runtime-dashboard/{path_text.lstrip('./')}"


def compare_vitest_results(
    baseline: Mapping[str, Any], raw_results_path: Path
) -> list[str]:
    """Require current failed test identities/signatures to be a baseline subset."""
    try:
        lifecycle = _c03_vitest_lifecycle_state(baseline)
    except ValueError as exc:
        return [f"vitest_c16_receipt_source_invalid:{exc}"]
    if lifecycle == "invalid":
        return ["vitest_lifecycle_receipt_invalid"]

    raw_bytes = raw_results_path.read_bytes()
    if lifecycle == "resolved":
        expected_sha256 = baseline["vitest"]["receipt_provenance"][
            "raw_receipt_sha256"
        ]
        actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        if actual_sha256 != expected_sha256:
            return [
                "vitest_resolved_receipt_hash_drift:"
                f"expected={expected_sha256}:actual={actual_sha256}"
            ]

    raw = json.loads(raw_bytes)
    baseline_rows: dict[tuple[str, str], tuple[str, str]] = {}
    for debt_class in baseline["vitest"]["debt_classes"]:
        for failure in debt_class["failures"]:
            baseline_rows[(failure["test_file"], failure["test_name"])] = (
                debt_class["class_id"],
                failure["assertion_anchor"],
            )
    errors: list[str] = []
    for test_result in raw.get("testResults", []):
        file_path = _normalise_vitest_path(
            test_result.get("name") or test_result.get("testFilePath") or ""
        )
        for assertion in test_result.get("assertionResults", []):
            if assertion.get("status") != "failed":
                continue
            canonical_name_parts = [
                *assertion.get("ancestorTitles", []),
                assertion.get("title", ""),
            ]
            full_name = (
                " > ".join(part for part in canonical_name_parts if part)
                or assertion.get("fullName")
                or ""
            )
            key = (file_path, full_name)
            if key not in baseline_rows:
                errors.append(f"vitest_new_failure:{file_path}:{full_name}")
                continue
            class_id, anchor = baseline_rows[key]
            messages = "\n".join(assertion.get("failureMessages", []))
            if anchor not in messages:
                errors.append(f"vitest_failure_signature_drift:{file_path}:{full_name}")
    return errors


def _validate_composition(
    unit: Mapping[str, Any], censuses: Mapping[str, Mapping[str, Any]], errors: list[str]
) -> None:
    unit_id = unit["unit_id"]
    disposition = unit["disposition"]
    strangle = unit["strangle_status"]
    census_id = unit.get("reference_census_id")
    successor = unit.get("successor")
    if disposition == "use_as_is" and strangle != "not_applicable":
        errors.append(f"use_as_is_strangle_invalid:{unit_id}")
    if disposition == "delete_pending" and (strangle != "pending" or census_id):
        errors.append(f"delete_pending_receipt_invalid:{unit_id}")
    if disposition == "deleted":
        if strangle != "strangled":
            errors.append(f"deleted_not_strangled:{unit_id}")
        census = censuses.get(census_id or "")
        if census is None:
            errors.append(f"deleted_census_missing:{unit_id}")
        elif census["result"] != "zero_consumers" or unit_id not in census["covers_unit_ids"]:
            errors.append(f"deleted_census_invalid:{unit_id}")
        elif not census.get("verification_refs"):
            errors.append(f"deleted_verification_receipt_missing:{unit_id}")
    if disposition == "rebind_pending" and strangle == "strangled":
        if successor is None:
            errors.append(f"rebound_successor_missing:{unit_id}")
        else:
            for consumer_ref in successor["consumer_refs"]:
                if not _path_from_ref(consumer_ref).exists():
                    errors.append(f"rebound_consumer_missing:{unit_id}:{consumer_ref}")
    elif successor is not None:
        errors.append(f"successor_on_non_rebound:{unit_id}")
    if disposition in {"wire_disposition", "retire_disposition"}:
        detail = unit.get("decision_detail")
        expected_kind = "wire" if disposition == "wire_disposition" else "retire"
        if detail is None or detail.get("kind") != expected_kind:
            errors.append(f"decision_detail_missing:{unit_id}")


def _validate_ui_primitives_mixed_receipt(
    entry: Mapping[str, Any], errors: list[str]
) -> None:
    """Recompute mixed C03b counts, decisions, and Git resurrection anchors."""
    receipt = entry.get("aggregate_disposition_receipt")
    if receipt is None:
        if entry.get("strangle_status") == "strangled":
            errors.append("ui_primitives_aggregate_receipt_missing")
        return

    members = receipt["c03b_members"]
    member_counts = Counter(member["disposition"] for member in members)
    recomputed = {
        "total": (
            len(UI_PRIMITIVES_PACKAGE_MIGRATED)
            + len(UI_PRIMITIVES_DASHBOARD_REBOUND)
            + len(members)
        ),
        "package_migrated": len(UI_PRIMITIVES_PACKAGE_MIGRATED),
        "dashboard_rebound": len(UI_PRIMITIVES_DASHBOARD_REBOUND),
        "retired": member_counts["retire"],
        "use_as_is": member_counts["use_as_is"],
        "c03b_candidates": len(members),
        "production_consumers": 0,
    }
    for key, value in recomputed.items():
        if receipt["counts"][key] != value:
            errors.append(f"ui_primitives_receipt_count_drift:{key}")

    members_by_name = {member["primitive"]: member for member in members}
    if set(members_by_name) != set(UI_PRIMITIVES_MEMBER_RULES):
        errors.append("ui_primitives_receipt_member_set_drift")
    else:
        for primitive, expected in UI_PRIMITIVES_MEMBER_RULES.items():
            if members_by_name[primitive] != {"primitive": primitive, **expected}:
                errors.append(f"ui_primitives_receipt_member_drift:{primitive}")

    anchor = receipt["pre_deletion_resurrection_anchor"]
    commit = anchor["git_commit"]
    if commit != UI_PRIMITIVES_PRE_DELETION_COMMIT:
        errors.append("ui_primitives_anchor_commit_drift")
    anchored_files = {item["path"]: item["git_blob"] for item in anchor["files"]}
    if set(anchored_files) != set(UI_PRIMITIVES_DELETED_BLOBS):
        errors.append("ui_primitives_anchor_file_set_drift")
        return
    for path, recorded_blob in anchored_files.items():
        completed = subprocess.run(
            ["git", "rev-parse", f"{commit}:policy-engine/{path}"],
            cwd=REPO_ROOT.parent,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            errors.append(f"ui_primitives_anchor_unresolved:{path}")
        elif completed.stdout.strip() != recorded_blob:
            errors.append(f"ui_primitives_anchor_blob_drift:{path}")


def _ui_primitives_source_state_errors(
    *,
    existing_paths: set[str],
    dashboard_exports: set[str],
    atlas_exports: set[str],
    production_consumers: Sequence[str],
    owner_refs: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """Return structural C03b retirement and resurrection failures."""
    errors: list[str] = []
    retired = {
        name
        for name, rule in UI_PRIMITIVES_MEMBER_RULES.items()
        if rule["disposition"] == "retire"
    }
    retained = set(UI_PRIMITIVES_MEMBER_RULES) - retired

    for primitive in sorted(retired):
        owner = f"apps/runtime-dashboard/src/shared/ui/{primitive}.tsx"
        test = f"apps/runtime-dashboard/src/shared/ui/{primitive}.a11y.test.tsx"
        if owner in existing_paths:
            errors.append(f"ui_primitives_retired_owner_revived:{primitive}")
        if test in existing_paths:
            errors.append(f"ui_primitives_retired_test_revived:{primitive}")
        if primitive in dashboard_exports:
            errors.append(f"ui_primitives_retired_export_revived:{primitive}")
        for reference in (owner_refs or {}).get(primitive, []):
            errors.append(
                f"ui_primitives_retired_symbol_revived:{primitive}:{reference}"
            )

    for primitive in sorted(retained):
        owner = f"apps/runtime-dashboard/src/shared/ui/{primitive}.tsx"
        test = f"apps/runtime-dashboard/src/shared/ui/{primitive}.a11y.test.tsx"
        if owner not in existing_paths:
            errors.append(f"ui_primitives_retained_owner_missing:{primitive}")
        if test not in existing_paths:
            errors.append(f"ui_primitives_retained_test_missing:{primitive}")
        if primitive not in dashboard_exports:
            errors.append(f"ui_primitives_retained_export_missing:{primitive}")
        if owner_refs is not None:
            dashboard_owner_refs = [
                ref
                for ref in owner_refs.get(primitive, [])
                if ref.startswith("apps/runtime-dashboard/src/shared/ui/")
            ]
            if not dashboard_owner_refs:
                errors.append(f"ui_primitives_retained_symbol_missing:{primitive}")

    for primitive in sorted(UI_PRIMITIVES_MEMBER_RULES):
        counterpart = f"packages/atlas-ui/src/primitives/{primitive}.tsx"
        if counterpart in existing_paths or primitive in atlas_exports:
            errors.append(
                f"ui_primitives_package_counterpart_without_consumer:{primitive}"
            )
        for reference in (owner_refs or {}).get(primitive, []):
            if reference.startswith("packages/atlas-ui/src/primitives/"):
                errors.append(
                    "ui_primitives_package_counterpart_without_consumer:"
                    f"{primitive}:{reference}"
                )

    for primitive in sorted(UI_PRIMITIVES_DASHBOARD_REBOUND):
        owner = f"apps/runtime-dashboard/src/shared/ui/{primitive}.tsx"
        if owner not in existing_paths:
            errors.append(f"ui_primitives_dashboard_rebound_missing:{primitive}")
        if primitive not in dashboard_exports:
            errors.append(f"ui_primitives_dashboard_rebound_export_missing:{primitive}")

    missing_package = sorted(UI_PRIMITIVES_PACKAGE_MIGRATED - atlas_exports)
    missing_define_once = sorted(ATLAS_UI_DEFINE_ONCE_PRIMITIVES - atlas_exports)
    missing_support = sorted(ATLAS_UI_SUPPORT_MODULES - atlas_exports)
    unexpected_package = sorted(
        atlas_exports
        - UI_PRIMITIVES_PACKAGE_MIGRATED
        - ATLAS_UI_DEFINE_ONCE_PRIMITIVES
        - ATLAS_UI_SUPPORT_MODULES
        - ATLAS_UI_OTHER_EXPORTS
    )
    if missing_package:
        errors.append(f"ui_primitives_package_exports_missing:{missing_package}")
    if missing_define_once:
        errors.append(
            f"atlas_ui_define_once_exports_missing:{missing_define_once}"
        )
    if missing_support:
        errors.append(f"atlas_ui_support_exports_missing:{missing_support}")
    if unexpected_package:
        errors.append(f"ui_primitives_package_exports_unexpected:{unexpected_package}")
    if production_consumers:
        errors.append(
            "ui_primitives_dormant_production_consumers:"
            + ",".join(production_consumers)
        )
    return errors


def _validate_ui_primitives_receipt_semantics(
    entry: Mapping[str, Any],
    ds2: Mapping[str, Any],
    censuses: Mapping[str, Mapping[str, Any]],
    errors: list[str],
    *,
    live_probes: bool,
) -> None:
    """Bind the C03b receipt to DS2, its census, successor, and live source."""
    receipt = entry.get("aggregate_disposition_receipt")
    if receipt is None:
        return
    if entry["disposition"] != "rebind_pending" or entry["strangle_status"] != "strangled":
        errors.append("ui_primitives_root_transition_invalid")
    if entry.get("reference_census_id") != UI_PRIMITIVES_CENSUS_ID:
        errors.append("ui_primitives_root_census_link_invalid")

    successor = entry.get("successor") or {}
    successor_refs = successor.get("consumer_refs", [])
    if successor.get("unit_id") != "atlas-ui-primitives" or ATLAS_UI_INDEX not in successor_refs:
        errors.append("ui_primitives_successor_root_invalid")
    direct_refs = [
        ref
        for ref in successor_refs
        if ref != ATLAS_UI_INDEX and (REPO_ROOT / ref.split(":", 1)[0]).is_file()
    ]
    errors.extend(_ui_primitives_successor_evidence_errors(direct_refs))

    ds2_by_id = {row["id"]: row for row in ds2["entries"]}
    ds2_titles = {row["title"] for row in ds2["entries"]}
    for primitive, expected in UI_PRIMITIVES_MEMBER_RULES.items():
        adoption_id = expected["ds2_adoption_id"]
        if adoption_id is None:
            if primitive in ds2_titles:
                errors.append(f"ui_primitives_ds2_absence_drift:{primitive}")
            continue
        row = ds2_by_id.get(adoption_id)
        if row is None or row["title"] != primitive:
            errors.append(f"ui_primitives_ds2_binding_drift:{primitive}")
        elif row["sunset_condition"] != expected["governing_condition"]:
            errors.append(f"ui_primitives_ds2_condition_drift:{primitive}")

    census = censuses.get(UI_PRIMITIVES_CENSUS_ID)
    if (
        census is None
        or census["covers_unit_ids"] != [UI_PRIMITIVES_ROOT_ID]
        or census["ds1_evidence_ids"] != [UI_PRIMITIVES_ROOT_ID]
        or census["result"] != "zero_consumers"
        or not census.get("verification_refs")
    ):
        errors.append("ui_primitives_census_invalid")
    else:
        scanner_probes = [
            probe
            for probe in census["probes"]
            if probe["kind"] == "typescript_symbol_consumer_census"
        ]
        if len(scanner_probes) != 1:
            errors.append("ui_primitives_scanner_probe_missing")
        else:
            probe = scanner_probes[0]
            if set(probe["targets"]) != set(UI_PRIMITIVES_MEMBER_RULES):
                errors.append("ui_primitives_scanner_targets_drift")
            if set(probe.get("checked_import_forms", [])) != UI_PRIMITIVES_CHECKED_IMPORT_FORMS:
                errors.append("ui_primitives_scanner_forms_drift")
            if probe["expected_count"] != 0 or probe["observed_refs"] != []:
                errors.append("ui_primitives_scanner_receipt_not_zero")

    if live_probes:
        errors.extend(_live_ui_primitives_source_state_errors())


def _validate_c15_mixed_receipt(
    entry: Mapping[str, Any],
    ds2: Mapping[str, Any],
    errors: list[str],
    *,
    live_probes: bool,
) -> None:
    """Bind the C15 mixed receipt to exact ownership and DS2 non-claims."""
    if entry["disposition"] != "rebind_pending" or entry["strangle_status"] != "strangled":
        errors.append("ui_compounds_root_mixed_transition_invalid")
    if entry["seed_rule"] != "ds4_c15_mixed_rebind_complete":
        errors.append("ui_compounds_root_mixed_seed_rule_invalid")
    if entry["rationale"] != C15_MIXED_RATIONALE:
        errors.append("ui_compounds_root_mixed_rationale_drift")

    successor = entry.get("successor") or {}
    if successor.get("unit_id") != C15_SUCCESSOR_ID:
        errors.append("ui_compounds_root_successor_invalid")
    if successor.get("consumer_refs") != C15_CONSUMER_REFS:
        errors.append("ui_compounds_root_consumer_refs_drift")

    ds2_by_id = {row["id"]: row for row in ds2["entries"]}
    transitional_condition = (
        "Keep the mapped live v4 family as the transitional winner until DS4 routes a real "
        "consumer through one governed replacement, DS6 passes its negative/browser/accessibility "
        "evidence, and the old import path is removed."
    )
    lineage_chart_condition = (
        "Archive admission alone sunsets nothing. DS4 may remove a mapped loser only after "
        "generated/source ownership, consumer migration, drift checks, and the owning slice's "
        "DS6 evidence are complete."
    )
    expected_ds2 = {
        "component-data-table": ("DataTable", transitional_condition),
        "component-metric-card": ("MetricCard", transitional_condition),
        "component-provenance-graph": ("ProvenanceGraph", transitional_condition),
        "viz-chart-provenance-lineage": (
            "Provenance Lineage chart",
            lineage_chart_condition,
        ),
    }
    for adoption_id, (title, condition) in expected_ds2.items():
        row = ds2_by_id.get(adoption_id)
        if row is None or row["title"] != title:
            errors.append(f"ui_compounds_root_ds2_binding_drift:{adoption_id}")
        elif row["sunset_condition"] != condition:
            errors.append(f"ui_compounds_root_ds2_condition_drift:{adoption_id}")

    if not live_probes:
        return

    for component in C15_PACKAGE_MIGRATED:
        package_owner = REPO_ROOT / f"packages/atlas-ui/src/compounds/{component}.tsx"
        dashboard_owner = REPO_ROOT / f"apps/runtime-dashboard/src/shared/ui/{component}.tsx"
        if not package_owner.is_file():
            errors.append(f"ui_compounds_root_package_owner_missing:{component}")
        if dashboard_owner.exists():
            errors.append(f"ui_compounds_root_dashboard_owner_survives:{component}")

    retired_dashboard_support = [
        "apps/runtime-dashboard/src/shared/ui/JsonPreview.test.tsx",
        "apps/runtime-dashboard/src/shared/ui/JsonPreview.a11y.test.tsx",
        "apps/runtime-dashboard/src/shared/ui/JsonPreview.stories.tsx",
        "apps/runtime-dashboard/src/shared/ui/VirtualList.a11y.test.tsx",
        "apps/runtime-dashboard/src/shared/ui/VirtualTable.a11y.test.tsx",
    ]
    for relative in retired_dashboard_support:
        if (REPO_ROOT / relative).exists():
            errors.append(f"ui_compounds_root_dashboard_support_survives:{relative}")

    for component in C15_DASHBOARD_USE_AS_IS:
        dashboard_owner = REPO_ROOT / f"apps/runtime-dashboard/src/shared/ui/{component}.tsx"
        package_counterpart = REPO_ROOT / f"packages/atlas-ui/src/compounds/{component}.tsx"
        if not dashboard_owner.is_file():
            errors.append(f"ui_compounds_root_transitional_owner_missing:{component}")
        if package_counterpart.exists():
            errors.append(f"ui_compounds_root_package_twin_created:{component}")

    package_exports = _owner_exports(
        ATLAS_UI_INDEX,
        (REPO_ROOT / ATLAS_UI_INDEX).read_text(encoding="utf-8"),
        "./compounds/",
    )
    if package_exports & C15_DASHBOARD_USE_AS_IS:
        errors.append("ui_compounds_root_transitional_export_created")
    if not C15_PACKAGE_MIGRATED <= package_exports:
        errors.append("ui_compounds_root_package_exports_missing")

    sources = _typescript_production_sources(
        [
            "apps/runtime-dashboard/src",
            "packages/atlas-ui/src",
            "packages/atlas-ui/tests",
        ]
    )
    consumer_map = _c15_migrated_consumer_map_from_sources(sources)
    errors.extend(_c15_migrated_consumer_errors(sources))
    successor_paths = set(successor.get("consumer_refs", []))
    for component, references in consumer_map.items():
        for reference in references:
            consumer_path = reference.split(":", 1)[0]
            if consumer_path not in successor_paths:
                errors.append(
                    "ui_compounds_root_live_consumer_ref_missing:"
                    f"{component}:{consumer_path}"
                )


def _validate_c16_mixed_receipt(
    entry: Mapping[str, Any],
    ds2: Mapping[str, Any],
    errors: list[str],
    *,
    live_probes: bool,
) -> None:
    """Bind the C16 mixed receipt to owners, consumers, and explicit non-claims."""
    if entry["disposition"] != "rebind_pending" or entry["strangle_status"] != "strangled":
        errors.append("ui_patterns_mixed_transition_invalid")
    if entry["seed_rule"] != "ds4_c16_mixed_rebind_complete":
        errors.append("ui_patterns_mixed_seed_rule_invalid")
    if entry["rationale"] != C16_MIXED_RATIONALE:
        errors.append("ui_patterns_mixed_rationale_drift")

    successor = entry.get("successor") or {}
    if successor.get("unit_id") != C16_SUCCESSOR_ID:
        errors.append("ui_patterns_successor_invalid")
    if successor.get("consumer_refs") != C16_CONSUMER_REFS:
        errors.append("ui_patterns_consumer_refs_drift")

    linked_ids = set(entry["evidence_link"]["ds2_adoption_ids"])
    if linked_ids != C16_FLOW_IDS:
        errors.append("ui_patterns_flow_id_set_drift")

    ds2_by_id = {row["id"]: row for row in ds2["entries"]}
    for flow_id in sorted(C16_FLOW_IDS):
        row = ds2_by_id.get(flow_id)
        if row is None:
            errors.append(f"ui_patterns_flow_missing:{flow_id}")
            continue
        if not row["reason"].startswith(C16_FLOW_REASON):
            errors.append(f"ui_patterns_flow_reason_drift:{flow_id}")
        next_adjudication = row.get("next_adjudication") or {}
        if next_adjudication.get("owner_slices") != C16_FLOW_OWNER_SLICES:
            errors.append(f"ui_patterns_flow_owner_drift:{flow_id}")
        if next_adjudication.get("completion_signal") != C16_FLOW_CLOSURE_SIGNAL:
            errors.append(f"ui_patterns_flow_closure_signal_drift:{flow_id}")

    responsive_condition = (
        "Revisit after DS4 binds the pattern to one breakpoint source and DS6 supplies its "
        "full browser/print/touch evidence cell."
    )
    search_field_condition = (
        "Revisit after the DS4 package has the governed export, a migrated live consumer, "
        "full state evidence, and a DS6 negative/e2e semantic test."
    )
    search_form_condition = (
        "Revisit after the owning slice binds typed producer data, recovery states, a live "
        "consumer, and DS6 keyboard/error-path evidence."
    )
    expected_nonclaims = {
        "responsive-layout-two-pane": responsive_condition,
        "responsive-layout-supporting-pane": responsive_condition,
        "component-search-field": search_field_condition,
        "form-search-source-selection": search_form_condition,
    }
    for adoption_id, condition in expected_nonclaims.items():
        row = ds2_by_id.get(adoption_id)
        if row is None or row["revisit_condition"] != condition:
            errors.append(f"ui_patterns_nonclaim_condition_drift:{adoption_id}")
        if adoption_id in linked_ids:
            errors.append(f"ui_patterns_false_ds2_claim:{adoption_id}")

    if not live_probes:
        return

    source_errors = _c16_pattern_source_state_errors()
    errors.extend(source_errors)
    consumer_map = _c16_pattern_consumer_map_from_sources(
        _typescript_production_sources(["apps/runtime-dashboard/src"])
    )
    successor_paths = set(successor.get("consumer_refs", []))
    for component, references in consumer_map.items():
        for consumer_path in references:
            if consumer_path not in successor_paths:
                errors.append(
                    f"ui_patterns_live_consumer_ref_missing:{component}:{consumer_path}"
                )


def _validate_c17_responsive_receipt(
    entry: Mapping[str, Any],
    token_entry: Mapping[str, Any],
    ds2: Mapping[str, Any],
    errors: list[str],
    *,
    live_probes: bool,
) -> None:
    """Bind C17 to one generated projection without claiming DS6 evidence."""
    if entry["disposition"] != "rebind_pending" or entry["strangle_status"] != "strangled":
        errors.append("ui_responsive_use_as_is_transition_invalid")
    if entry["seed_rule"] != "ds4_c17_generated_breakpoint_use_as_is":
        errors.append("ui_responsive_use_as_is_seed_rule_invalid")
    if entry["rationale"] != C17_RATIONALE:
        errors.append("ui_responsive_use_as_is_rationale_drift")

    successor = entry.get("successor") or {}
    if successor.get("unit_id") != C17_SUCCESSOR_ID:
        errors.append("ui_responsive_successor_invalid")
    if successor.get("consumer_refs") != C17_CONSUMER_REFS:
        errors.append("ui_responsive_consumer_refs_drift")

    if (
        token_entry["disposition"] != "rebind_pending"
        or token_entry["strangle_status"] != "pending"
        or token_entry.get("successor") is not None
    ):
        errors.append("ui_tokens_false_c17_transition")

    ds2_by_id = {row["id"]: row for row in ds2["entries"]}
    taxonomy = ds2_by_id.get("responsive-breakpoint-taxonomy") or {}
    if taxonomy.get("adoption_verdict") != "reject":
        errors.append("ui_responsive_rejected_taxonomy_drift")

    responsive_ids = {
        adoption_id
        for adoption_id in entry["evidence_link"]["ds2_adoption_ids"]
        if adoption_id.startswith("responsive-")
    }
    ds6_prohibition = "claiming browser or manual assistive-technology evidence"
    for adoption_id in sorted(
        responsive_ids - {"responsive-breakpoint-taxonomy", "responsive-shell-navigation"}
    ):
        row = ds2_by_id.get(adoption_id) or {}
        if row.get("adoption_verdict") != "admit_after_refactor":
            errors.append(f"ui_responsive_ds2_verdict_drift:{adoption_id}")
        if "DS6" not in row.get("consuming_surfaces", []):
            errors.append(f"ui_responsive_ds6_owner_drift:{adoption_id}")
        if ds6_prohibition not in (row.get("authority") or {}).get("may_not_use_for", []):
            errors.append(f"ui_responsive_ds6_evidence_boundary_drift:{adoption_id}")

    for evidence_id in sorted(C17_EVIDENCE_IDS):
        row = ds2_by_id.get(evidence_id) or {}
        if row.get("adoption_verdict") != "admit_after_refactor":
            errors.append(f"ui_responsive_bounded_evidence_drift:{evidence_id}")
        if ds6_prohibition not in (row.get("authority") or {}).get("may_not_use_for", []):
            errors.append(f"ui_responsive_bounded_evidence_overclaim:{evidence_id}")

    if live_probes:
        errors.extend(_c17_responsive_source_state_errors())


def _validate_producer_binding_debt_findings(
    data: Mapping[str, Any], errors: list[str]
) -> None:
    """Bind every producer-debt row byte-for-byte to its sole descriptor."""
    rows = data.get("supplemental_findings", [])
    if not isinstance(rows, list):
        return
    by_id = {
        str(row.get("finding_id")): row
        for row in rows
        if isinstance(row, Mapping)
    }
    producer_rows = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get("finding_kind") == "producer_binding_debt"
    ]
    for finding_id, descriptor in PRODUCER_BINDING_DEBT_DESCRIPTORS.items():
        row = by_id.get(finding_id)
        if row is None:
            errors.append(
                f"producer_binding_debt_drift:{finding_id}:finding_id"
            )
            continue
        expected = {
            "finding_id": finding_id,
            **descriptor,
            "decision_date": descriptor.get("decision_date", DECISION_DATE),
        }
        for field, expected_value in expected.items():
            if row.get(field) != expected_value:
                errors.append(
                    f"producer_binding_debt_drift:{finding_id}:{field}"
                )
    descriptor_ids = set(PRODUCER_BINDING_DEBT_DESCRIPTORS)
    for row in producer_rows:
        finding_id = str(row.get("finding_id", "unknown"))
        if finding_id not in descriptor_ids:
            errors.append(
                "producer_binding_debt_descriptor_missing:" + finding_id
            )


def _validate_raw_transport_drift(
    data: Mapping[str, Any],
    errors: list[str],
    *,
    sources: Mapping[str, str] | None = None,
) -> None:
    """Compare the typed C03a receipt with the bounded live syntax census."""
    rows = data.get("supplemental_findings", [])
    if not isinstance(rows, list):
        return
    row = next(
        (
            item
            for item in rows
            if isinstance(item, Mapping)
            and item.get("finding_id") == RAW_TRANSPORT_DRIFT_FINDING_ID
        ),
        None,
    )
    if row is None:
        return
    receipt = row.get("raw_transport_receipt")
    if not isinstance(receipt, Mapping):
        return
    live_receipt = receipt.get("live_direct_constructor_census")
    if not isinstance(live_receipt, Mapping):
        return
    observed = _direct_transport_census(sources)
    expected = {
        "fetch_calls": observed["kind_counts"]["fetch"],
        "fetch_production_file_count": observed["fetch_production_file_count"],
        "direct_constructor_count": observed["direct_constructor_count"],
        "direct_constructor_production_file_count": observed["production_file_count"],
        "kind_counts": observed["kind_counts"],
    }
    if live_receipt != expected:
        errors.append("raw_transport_live_direct_constructor_census_drift")


def _validate_integrate_contract_debt_findings(
    data: Mapping[str, Any], errors: list[str]
) -> None:
    """Bind external-owner integrate debt byte-for-byte to its typed contract."""
    rows = data.get("supplemental_findings", [])
    if not isinstance(rows, list):
        return
    by_id = {
        str(row.get("finding_id")): row
        for row in rows
        if isinstance(row, Mapping)
    }
    integrate_rows = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get("finding_kind") == "integrate_contract_debt"
    ]
    for finding_id, descriptor in INTEGRATE_DEBT_DESCRIPTORS.items():
        row = by_id.get(finding_id)
        if row is None:
            errors.append(
                f"integrate_contract_debt_drift:{finding_id}:finding_id"
            )
            continue
        for field, expected_value in descriptor.items():
            if row.get(field) != expected_value:
                errors.append(
                    f"integrate_contract_debt_drift:{finding_id}:{field}"
                )
    descriptor_ids = set(INTEGRATE_DEBT_DESCRIPTORS)
    for row in integrate_rows:
        finding_id = str(row.get("finding_id", "unknown"))
        if finding_id not in descriptor_ids:
            errors.append(
                "integrate_contract_debt_descriptor_missing:" + finding_id
            )


def _validate_c23_containment_roots(
    entries: Mapping[str, Mapping[str, Any]], errors: list[str]
) -> None:
    """Bind all deleted readiness/scientific roots to one containment receipt."""
    for unit_id in C23_ROOT_IDS:
        entry = entries.get(unit_id, {})
        successor = entry.get("successor") or {}
        if (
            entry.get("disposition") != "rebind_pending"
            or entry.get("strangle_status") != "strangled"
            or entry.get("owner_slice") != "DS4"
            or entry.get("seed_rule") != "ds4_c23_containment"
            or entry.get("rationale") != C23_RATIONALE
            or successor.get("unit_id") != C23_SUCCESSOR_ID
            or successor.get("consumer_refs") != C23_SUCCESSOR_REFS
        ):
            errors.append(f"c23_containment_root_drift:{unit_id}")


def _validate_c11b_query_memory_root(
    entries: Mapping[str, Mapping[str, Any]], errors: list[str]
) -> None:
    """Bind the generic query root to C12b's owner and C11b's sole live consumer."""
    entry = entries.get(C11B_QUERY_MEMORY_ROOT_ID, {})
    expected_fields = {
        "disposition": "rebind_pending",
        "strangle_status": "strangled",
        "owner": "team-architecture",
        "owner_slice": "DS5",
        "seed_rule": "ds1_incomplete_rebind_pending",
        "rationale": C11B_QUERY_MEMORY_RATIONALE,
    }
    for field, expected in expected_fields.items():
        if entry.get(field) != expected:
            errors.append(f"c11b_query_memory_root_drift:{field}")
    successor = entry.get("successor")
    if not isinstance(successor, Mapping):
        errors.append("c11b_query_memory_root_drift:successor")
        return
    if successor.get("unit_id") != C11B_QUERY_MEMORY_SUCCESSOR_ID:
        errors.append("c11b_query_memory_root_drift:successor.unit_id")
    if successor.get("consumer_refs") != C11B_QUERY_MEMORY_SUCCESSOR_REFS:
        errors.append("c11b_query_memory_root_drift:successor.consumer_refs")


def _validate_c13_print_export_root(
    entries: Mapping[str, Mapping[str, Any]], errors: list[str]
) -> None:
    """Bind the exact C13 predecessor closure to its independent receipt."""
    try:
        receipt = _c13_independent_print_receipt()
        expected = _c13_print_closed_entry(receipt)
    except (OSError, ValueError) as exc:
        errors.append(f"c13_print_receipt_invalid:{exc}")
        return
    if entries.get(C13_PRINT_ROOT_ID) != expected:
        errors.append("c13_print_export_root_drift")


def _validate_storage_construction_census(
    data: Mapping[str, Any], errors: list[str]
) -> None:
    """Bind every explicit persistence class to its finite owner contract."""
    census = data.get("storage_construction_census")
    if not isinstance(census, Mapping):
        errors.append("storage_construction_census_missing")
        return
    sites = census.get("sites")
    if not isinstance(sites, list):
        errors.append("storage_construction_sites_invalid")
        return
    if census.get("rows_sha256") != "sha256:" + _canonical_sha256(sites):
        errors.append("storage_construction_rows_digest_drift")
    for field, expected in C17B_AUTHORITY_FLOW_LIMITATION.items():
        if census.get(field) != expected:
            errors.append(f"storage_construction_authority_flow_limit_drift:{field}")
    factory_receipts = census.get("authority_factory_receipts")
    if not isinstance(factory_receipts, list):
        errors.append("storage_construction_factory_receipts_invalid")
        factory_receipts = []
    if census.get("authority_factory_count") != len(factory_receipts):
        errors.append("storage_construction_factory_count_drift")
    if census.get("authority_factory_receipts_sha256") != (
        "sha256:" + _canonical_sha256(factory_receipts)
    ):
        errors.append("storage_construction_factory_receipts_digest_drift")
    factory_ids: list[str] = []
    for raw_receipt in factory_receipts:
        if not isinstance(raw_receipt, Mapping):
            errors.append("storage_construction_factory_receipt_invalid")
            continue
        receipt_id = str(raw_receipt.get("factory_site_id", "unknown"))
        factory_ids.append(receipt_id)
        factory_path = _path_from_ref(str(raw_receipt.get("path", "")))
        if not factory_path.is_file():
            errors.append(f"storage_construction_factory_source_missing:{receipt_id}")
        elif raw_receipt.get("source_fingerprint") != _sha256(factory_path):
            errors.append(
                f"storage_construction_factory_source_fingerprint_drift:{receipt_id}"
            )
    duplicate_factory_ids = sorted(
        receipt_id
        for receipt_id, count in Counter(factory_ids).items()
        if count > 1
    )
    errors.extend(
        f"storage_construction_duplicate_factory_id:{receipt_id}"
        for receipt_id in duplicate_factory_ids
    )
    site_ids: list[str] = []
    classes: Counter[str] = Counter()
    for raw_row in sites:
        if not isinstance(raw_row, Mapping):
            errors.append("storage_construction_row_invalid")
            continue
        row = raw_row
        site_id = str(row.get("site_id", "unknown"))
        site_ids.append(site_id)
        classification = str(row.get("classification", "unknown"))
        classes[classification] += 1
        path = str(row.get("path", ""))
        store_owner = str(row.get("store_owner", ""))
        source_path = _path_from_ref(path)
        if not source_path.is_file():
            errors.append(f"storage_construction_source_missing:{site_id}")
        elif row.get("source_fingerprint") != _sha256(source_path):
            errors.append(f"storage_construction_source_fingerprint_drift:{site_id}")
        if not _path_from_ref(store_owner).is_file():
            errors.append(f"storage_construction_store_owner_missing:{site_id}")
        if "authority_binding" in row:
            errors.append(f"storage_construction_retired_authority_binding:{site_id}")

        if classification == "scoped_authority":
            if row.get("scoped_envelope_owner") != C17B_SCOPED_ENVELOPE_OWNER:
                errors.append(f"storage_construction_scoped_owner_drift:{site_id}")
            expected_codec = C17B_REGISTERED_CODEC_BY_OWNER.get(store_owner)
            if expected_codec is None or row.get("registered_codec_id") != expected_codec:
                errors.append(f"storage_construction_codec_owner_drift:{site_id}")
        elif classification == "interaction_benign":
            expected_reason = C17B_BENIGN_REASON_BY_OWNER.get(store_owner)
            if store_owner != path or row.get("benign_reason") != expected_reason:
                errors.append(f"storage_construction_benign_owner_drift:{site_id}")
            for field in (
                "capability_states",
                "closure_signal",
                "owner_slice",
                "registered_codec_id",
                "scoped_envelope_owner",
            ):
                if field in row:
                    errors.append(
                        f"storage_construction_benign_debt_field:{site_id}:{field}"
                    )
        elif classification == "rollout_cache_pending":
            pass
        else:
            errors.append(f"storage_construction_class_invalid:{site_id}")

    duplicates = sorted(
        site_id for site_id, count in Counter(site_ids).items() if count > 1
    )
    errors.extend(
        f"storage_construction_duplicate_site_id:{site_id}" for site_id in duplicates
    )
    observed_class_counts = {
        classification: classes.get(classification, 0)
        for classification in C17B_STORAGE_CLASS_COUNTS
    }
    if (
        observed_class_counts != C17B_STORAGE_CLASS_COUNTS
        or set(classes) - set(C17B_STORAGE_CLASS_COUNTS)
    ):
        errors.append("storage_construction_class_distribution_drift")


def _validate_ds9_c07_adjudication(
    data: Mapping[str, Any],
    entries: Mapping[str, Mapping[str, Any]],
    errors: list[str],
) -> None:
    """Bind every one of the 13 root and five authority rulings."""
    for unit_id, scope in DS9_C07_ROOT_SCOPE.items():
        entry = entries.get(unit_id)
        if not isinstance(entry, Mapping):
            errors.append(f"ds9_c07_root_missing:{unit_id}")
            continue
        formal = DS9_C07_ROOT_FORMAL[unit_id]
        successor = entry.get("successor")
        successor_unit_id = successor.get("unit_id") if isinstance(successor, Mapping) else None
        observed = {
            "disposition": entry.get("disposition"),
            "strangle_status": entry.get("strangle_status"),
            "owner": entry.get("owner"),
            "owner_slice": entry.get("owner_slice"),
            "successor_unit_id": successor_unit_id,
            "reference_census_id": entry.get("reference_census_id"),
        }
        if observed != formal:
            errors.append(f"ds9_c07_root_formal_drift:{unit_id}")
        expected_metadata = {
            "decision_date": DS9_C07_DECISION_DATE,
            "seed_rule": DS9_C07_SCOPE_SEED_RULE[scope],
            "rationale": DS9_C07_ROOT_RATIONALES[unit_id],
        }
        for field, expected in expected_metadata.items():
            if entry.get(field) != expected:
                errors.append(f"ds9_c07_root_scope_drift:{unit_id}:{field}")
        if entry.get("family_complete") is not None:
            errors.append(f"ds9_c07_root_family_complete_claim:{unit_id}")
    local_successor = entries.get("cache-local-disputes", {}).get("successor")
    if (
        not isinstance(local_successor, Mapping)
        or local_successor.get("consumer_refs") != DS9_C07_LOCAL_DISPUTE_SUCCESSOR_REFS
    ):
        errors.append("ds9_c07_local_dispute_successor_drift")

    supplemental = data.get("supplemental_findings", [])
    if not isinstance(supplemental, list):
        errors.append("ds9_c07_supplemental_container_invalid")
        return
    counts = Counter(
        str(row.get("finding_id"))
        for row in supplemental
        if isinstance(row, Mapping) and row.get("finding_id") in DS9_C07_AUTHORITY_FINDING_IDS
    )
    if set(counts) != DS9_C07_AUTHORITY_FINDING_IDS or any(count != 1 for count in counts.values()):
        errors.append("ds9_c07_authority_finding_denominator_drift")
    for row in supplemental:
        if (
            not isinstance(row, Mapping)
            or row.get("finding_id") not in DS9_C07_AUTHORITY_FINDING_IDS
        ):
            continue
        finding_id = str(row["finding_id"])
        expected = {
            "decision_date": DS9_C07_DECISION_DATE,
            "disposition": "rebind_pending",
            "owner_slice": "DS9",
            "status": "open_debt",
        }
        for field, value in expected.items():
            if row.get(field) != value:
                errors.append(f"ds9_c07_authority_finding_drift:{finding_id}:{field}")
    if len(DS9_C07_ROOT_SCOPE) + len(counts) != 18:
        errors.append("ds9_c07_adjudication_denominator_drift")


def _ds18_time_semantics_scan() -> dict[str, Any]:
    """Run the complete TypeScript AST render/export census."""
    completed = subprocess.run(
        [
            os.environ.get("POLISYOS_NODE_EXECUTABLE", "node"),
            str(DS18_TIME_SEMANTICS_SCANNER_PATH),
            "--repo-root",
            str(REPO_ROOT),
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            "DS18 time-semantics scanner failed: " + completed.stderr.strip()
        )
    result = json.loads(completed.stdout)
    if result.get("schema_id") != "polisyos.atlas.ds18-time-semantics-scan.v1":
        raise ValueError("DS18 time-semantics scanner schema drift")
    return result


def _ds18_source_receipt(path_ref: str) -> dict[str, str]:
    """Bind a current source/test path to its exact bytes."""
    path = REPO_ROOT / path_ref
    if not path.is_file():
        raise ValueError(f"DS18 evidence path is not a file: {path_ref}")
    return {
        "path": path_ref,
        "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _ds18_primary_direct_roots(scan: Mapping[str, Any]) -> dict[str, str]:
    """Resolve one independently reviewed direct DS4 root per direct file."""
    resolved: dict[str, str] = {}
    files = {
        str(row["path"]): row
        for row in scan.get("files", [])
        if isinstance(row, Mapping)
    }
    for path_ref in sorted(DS18_TIME_SEMANTICS_DIRECT_FILES):
        row = files.get(path_ref)
        if not isinstance(row, Mapping):
            raise ValueError(f"DS18 direct file absent from scanner: {path_ref}")
        matching = [
            root
            for root in row.get("roots", [])
            if isinstance(root, Mapping)
            and int(root.get("time_semantics_label_render_count", 0)) > 0
        ]
        if len(matching) != 1:
            raise ValueError(
                f"DS18 direct file requires one TimeSemanticsLabel root: "
                f"{path_ref}:{len(matching)}"
            )
        resolved[path_ref] = str(matching[0]["root_id"])
    return resolved


def _ds18_behavioral_evidence(path_ref: str) -> list[dict[str, str]]:
    """Return content-bound executable evidence for one reconciled surface file."""
    return [
        {
            **_ds18_source_receipt(test_ref),
            "assertion_id": "state-mutation-keeps-shell-and-changes-time-semantics",
        }
        for test_ref in DS18_TIME_SEMANTICS_BEHAVIOR_TESTS[path_ref]
    ]


def _build_ds18_time_semantics_coverage(
    scan: Mapping[str, Any],
    *,
    frontend_freeze_commit: str | None = None,
) -> dict[str, Any]:
    """Build explicit per-file/per-root receipts from the reconciled C06 census."""
    primary_roots = _ds18_primary_direct_roots(scan)
    file_rows = {
        str(row["path"]): row
        for row in scan.get("files", [])
        if isinstance(row, Mapping)
    }

    def owner_for(path_ref: str) -> tuple[str, str] | None:
        owner_path = DS18_TIME_SEMANTICS_CROSS_FILE_INHERITANCE.get(path_ref)
        if owner_path is not None:
            return owner_path, primary_roots[owner_path]
        own_root = primary_roots.get(path_ref)
        return (path_ref, own_root) if own_root is not None else None

    files: list[dict[str, Any]] = []
    obligated_roots = 0
    covered_roots = 0
    decision_roots = 0
    inherited_roots = 0
    for scan_file in scan.get("files", []):
        path_ref = str(scan_file["path"])
        owner = owner_for(path_ref)
        roots: list[dict[str, Any]] = []
        for scanned_root in scan_file.get("roots", []):
            root = dict(scanned_root)
            root.update(
                {
                    "owner_evidence": [_ds18_source_receipt(path_ref)],
                    "predicate_provenance": "independently_reconciled",
                    "reviewer_receipt": DS18_TIME_SEMANTICS_REVIEWER,
                }
            )
            root_id = str(scanned_root["root_id"])
            if path_ref in DS18_TIME_SEMANTICS_STRICT_PROJECTION_FILES:
                classification = "decision_bearing"
                temporal_binding = "strict_non_jsx_projection"
            elif path_ref in primary_roots and root_id == primary_roots[path_ref]:
                classification = "decision_bearing"
                temporal_binding = "direct_ds4"
            elif owner is not None:
                classification = "inherits_admitted_dom"
                temporal_binding = None
            else:
                classification = "non_decision_bearing"
                temporal_binding = None
            root["classification"] = classification
            if classification == "decision_bearing":
                decision_roots += 1
                obligated_roots += 1
                covered_roots += 1
                root["behavioral_evidence"] = _ds18_behavioral_evidence(path_ref)
                root["temporal_binding"] = temporal_binding
                root["temporal_obligation"] = "as_of_epoch_validity"
            elif classification == "inherits_admitted_dom":
                inherited_roots += 1
                obligated_roots += 1
                covered_roots += 1
                if owner is None:  # pragma: no cover - construction guard
                    raise ValueError(f"DS18 inherited root has no owner: {path_ref}")
                root["behavioral_evidence"] = _ds18_behavioral_evidence(path_ref)
                root["inherited_from"] = {
                    "path": owner[0],
                    "root_id": owner[1],
                }
                root["temporal_obligation"] = "as_of_epoch_validity"
            else:
                root["behavioral_evidence"] = []
                root["non_decision_reason"] = (
                    "independently reviewed as layout, interaction, editor, "
                    "diagnostic, or candidate-only rendering without an "
                    "admissibility-changing recommendation/status/limitation/quantity"
                )
            roots.append(root)
        files.append(
            {
                "path": path_ref,
                "predicate_provenance": "independently_reconciled",
                "receipt_kind": scan_file["receipt_kind"],
                "reviewer_receipt": DS18_TIME_SEMANTICS_REVIEWER,
                "roots": roots,
                "source_sha256": scan_file["source_sha256"],
            }
        )
    scanner_receipt = _ds18_source_receipt(DS18_TIME_SEMANTICS_SCANNER_REF)
    return {
        "schema_id": DS18_TIME_SEMANTICS_SCHEMA_ID,
        "owner_slice": "DS18",
        "predicate_provenance": "independently_reconciled",
        "source_root": scan["source_root"],
        "exclusion_policy": scan["exclusion_policy"],
        "scanner": scanner_receipt,
        "source_file_count": scan["file_count"],
        "root_count": scan["root_count"],
        "file_manifest_sha256": scan["file_manifest_sha256"],
        "root_manifest_sha256": scan["root_manifest_sha256"],
        "decision_bearing_root_count": decision_roots,
        "inherits_admitted_dom_root_count": inherited_roots,
        "obligated_root_count": obligated_roots,
        "covered_root_count": covered_roots,
        "frontend_freeze_commit": frontend_freeze_commit,
        "landing_slice_rule": DS18_TIME_SEMANTICS_LANDING_RULE,
        "landing_slice_checker": (
            "architecture/atlas_surfaces/check_frontend_disposition_register.py "
            "--check"
        ),
        "files": files,
    }


def _ds18_evidence_errors(
    evidence: object,
    *,
    root_label: str,
) -> list[str]:
    """Reject absent or stale executable/root evidence."""
    errors: list[str] = []
    if not isinstance(evidence, list) or not evidence:
        return [f"ds18_time_semantics_behavioral_evidence_missing:{root_label}"]
    for row in evidence:
        if not isinstance(row, Mapping):
            errors.append(
                f"ds18_time_semantics_behavioral_evidence_invalid:{root_label}"
            )
            continue
        path_ref = str(row.get("path", ""))
        path = REPO_ROOT / path_ref
        if not path.is_file():
            errors.append(
                f"ds18_time_semantics_behavioral_evidence_missing:{root_label}:{path_ref}"
            )
            continue
        observed = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if row.get("sha256") != observed:
            errors.append(
                f"ds18_time_semantics_behavioral_evidence_drift:{root_label}:{path_ref}"
            )
    return errors


def _validate_ds18_time_semantics_coverage_core(
    coverage: object,
    scan: Mapping[str, Any],
    errors: list[str],
    *,
    post_freeze_is_landing_red: bool,
) -> None:
    """Validate composition, current bytes, and independently reconciled roots."""
    if not isinstance(coverage, Mapping):
        errors.append("ds18_time_semantics_coverage_missing")
        return
    expected_header = {
        "schema_id": DS18_TIME_SEMANTICS_SCHEMA_ID,
        "owner_slice": "DS18",
        "predicate_provenance": "independently_reconciled",
        "source_root": scan.get("source_root"),
        "source_file_count": scan.get("file_count"),
        "root_count": scan.get("root_count"),
        "file_manifest_sha256": scan.get("file_manifest_sha256"),
        "root_manifest_sha256": scan.get("root_manifest_sha256"),
        "landing_slice_rule": DS18_TIME_SEMANTICS_LANDING_RULE,
    }
    for field, expected in expected_header.items():
        if coverage.get(field) != expected:
            suffix = (
                "landing_slice_reconciliation_required"
                if post_freeze_is_landing_red
                and field
                in {
                    "source_file_count",
                    "root_count",
                    "file_manifest_sha256",
                    "root_manifest_sha256",
                }
                else "coverage_header_drift"
            )
            errors.append(f"ds18_time_semantics_{suffix}:{field}")
    if coverage.get("exclusion_policy") != scan.get("exclusion_policy"):
        errors.append("ds18_time_semantics_exclusion_policy_drift")
    scanner = coverage.get("scanner")
    if scanner != _ds18_source_receipt(DS18_TIME_SEMANTICS_SCANNER_REF):
        errors.append("ds18_time_semantics_scanner_receipt_drift")

    stored_files = coverage.get("files")
    if not isinstance(stored_files, list):
        errors.append("ds18_time_semantics_files_invalid")
        return
    stored_by_path = {
        str(row.get("path")): row
        for row in stored_files
        if isinstance(row, Mapping)
    }
    scanned_by_path = {
        str(row.get("path")): row
        for row in scan.get("files", [])
        if isinstance(row, Mapping)
    }
    if set(stored_by_path) != set(scanned_by_path):
        suffix = (
            "landing_slice_reconciliation_required"
            if post_freeze_is_landing_red
            else "file_denominator_drift"
        )
        errors.append(
            f"ds18_time_semantics_{suffix}:"
            f"missing={sorted(set(scanned_by_path)-set(stored_by_path))}:"
            f"extra={sorted(set(stored_by_path)-set(scanned_by_path))}"
        )

    all_roots: dict[tuple[str, str], Mapping[str, Any]] = {}
    scanned_roots: dict[tuple[str, str], Mapping[str, Any]] = {}
    for path_ref, scanned_file in scanned_by_path.items():
        for root in scanned_file.get("roots", []):
            if isinstance(root, Mapping):
                scanned_roots[(path_ref, str(root.get("root_id")))] = root
    for path_ref, stored_file in stored_by_path.items():
        if stored_file.get("predicate_provenance") != "independently_reconciled":
            errors.append(f"ds18_time_semantics_file_provenance_drift:{path_ref}")
        scanned_file = scanned_by_path.get(path_ref)
        if scanned_file is None:
            continue
        for field in ("receipt_kind", "source_sha256"):
            if stored_file.get(field) != scanned_file.get(field):
                errors.append(f"ds18_time_semantics_file_receipt_drift:{path_ref}:{field}")
        stored_roots = stored_file.get("roots")
        if not isinstance(stored_roots, list):
            errors.append(f"ds18_time_semantics_roots_invalid:{path_ref}")
            continue
        stored_root_ids = {
            str(root.get("root_id"))
            for root in stored_roots
            if isinstance(root, Mapping)
        }
        scanned_root_ids = {
            str(root.get("root_id"))
            for root in scanned_file.get("roots", [])
            if isinstance(root, Mapping)
        }
        if stored_root_ids != scanned_root_ids:
            errors.append(f"ds18_time_semantics_root_inventory_drift:{path_ref}")
        for root in stored_roots:
            if not isinstance(root, Mapping):
                continue
            root_id = str(root.get("root_id"))
            label = f"{path_ref}:{root_id}"
            scanned_root = scanned_roots.get((path_ref, root_id))
            if scanned_root is None:
                continue
            scanner_fields = {
                "column",
                "component_identity",
                "epoch_context_read_count",
                "epoch_semantics_prop_count",
                "epoch_semantics_provider_render_count",
                "kind",
                "line",
                "root_id",
                "root_source_sha256",
                "time_semantics_label_render_count",
            }
            for field in scanner_fields:
                if root.get(field) != scanned_root.get(field):
                    errors.append(
                        f"ds18_time_semantics_root_receipt_drift:{label}:{field}"
                    )
            if root.get("predicate_provenance") != "independently_reconciled":
                errors.append(f"ds18_time_semantics_root_provenance_drift:{label}")
            if root.get("reviewer_receipt") != DS18_TIME_SEMANTICS_REVIEWER:
                errors.append(f"ds18_time_semantics_reviewer_receipt_drift:{label}")
            all_roots[(path_ref, root_id)] = root

    decision_count = 0
    inherited_count = 0
    covered_count = 0
    for (path_ref, root_id), root in all_roots.items():
        label = f"{path_ref}:{root_id}"
        classification = root.get("classification")
        if classification == "decision_bearing":
            decision_count += 1
            covered_count += 1
            if root.get("temporal_obligation") != "as_of_epoch_validity":
                errors.append(f"ds18_time_semantics_obligation_drift:{label}")
            binding = root.get("temporal_binding")
            if binding == "direct_ds4":
                if int(root.get("time_semantics_label_render_count", 0)) < 1:
                    errors.append(f"ds18_time_semantics_direct_ds4_render_missing:{label}")
            elif binding != "strict_non_jsx_projection":
                errors.append(f"ds18_time_semantics_binding_invalid:{label}")
            errors.extend(
                _ds18_evidence_errors(root.get("behavioral_evidence"), root_label=label)
            )
        elif classification == "inherits_admitted_dom":
            inherited_count += 1
            covered_count += 1
            inherited_from = root.get("inherited_from")
            if not isinstance(inherited_from, Mapping):
                errors.append(f"ds18_time_semantics_inherited_owner_missing:{label}")
            else:
                owner_key = (
                    str(inherited_from.get("path")),
                    str(inherited_from.get("root_id")),
                )
                owner = all_roots.get(owner_key)
                if owner is None or owner.get("classification") != "decision_bearing":
                    errors.append(f"ds18_time_semantics_inherited_owner_invalid:{label}")
            errors.extend(
                _ds18_evidence_errors(root.get("behavioral_evidence"), root_label=label)
            )
        elif classification == "non_decision_bearing":
            if not str(root.get("non_decision_reason", "")).strip():
                errors.append(f"ds18_time_semantics_nondecision_reason_missing:{label}")
        else:
            errors.append(f"ds18_time_semantics_root_unclassified:{label}")
    expected_counts = {
        "decision_bearing_root_count": decision_count,
        "inherits_admitted_dom_root_count": inherited_count,
        "obligated_root_count": decision_count + inherited_count,
        "covered_root_count": covered_count,
    }
    for field, expected in expected_counts.items():
        if coverage.get(field) != expected:
            errors.append(f"ds18_time_semantics_count_drift:{field}")
    if decision_count + inherited_count == 0:
        errors.append("ds18_time_semantics_empty_obligation_denominator")


def _validate_ds18_time_semantics_coverage(
    data: Mapping[str, Any],
    errors: list[str],
    *,
    scan: Mapping[str, Any] | None = None,
) -> None:
    """Validate the current denominator; post-freeze growth is the landing red."""
    current_scan = scan if scan is not None else _ds18_time_semantics_scan()
    coverage = data.get("ds18_time_semantics_coverage")
    frozen = (
        isinstance(coverage, Mapping)
        and isinstance(coverage.get("frontend_freeze_commit"), str)
    )
    _validate_ds18_time_semantics_coverage_core(
        coverage,
        current_scan,
        errors,
        post_freeze_is_landing_red=frozen,
    )


def _validate_ds18_historical_time_semantics_coverage(
    coverage: Mapping[str, Any],
    frozen_scan: Mapping[str, Any],
    errors: list[str],
) -> None:
    """Keep the exact DS18 freeze independently replayable after later growth."""
    _validate_ds18_time_semantics_coverage_core(
        coverage,
        frozen_scan,
        errors,
        post_freeze_is_landing_red=False,
    )


def validate_register(
    data: Mapping[str, Any],
    *,
    live_probes: bool = True,
    schema: bool = True,
    report_parity: bool = True,
    direct_transport_sources: Mapping[str, str] | None = None,
    baseline_manifest: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return all schema, parity, composition, and live-census failures."""
    errors: list[str] = []
    _validate_producer_binding_debt_findings(data, errors)
    if live_probes or direct_transport_sources is not None:
        _validate_raw_transport_drift(
            data,
            errors,
            sources=direct_transport_sources,
        )
    _validate_integrate_contract_debt_findings(data, errors)
    errors.extend(
        _authority_presentation_errors(data, live_probes=live_probes)
    )
    try:
        generated_supplemental = _supplemental_findings()
    except ValueError as exc:
        errors.append(f"supplemental_source_invalid:{exc}")
        generated_supplemental = []
    _validate_ds6_register_transition_findings(
        data,
        errors,
        generated_supplemental,
    )
    _validate_ds11_trust_presentation_transition_findings(data, errors)
    supplemental_rows = data.get("supplemental_findings", [])
    if isinstance(supplemental_rows, list):
        supplemental_ids = [
            str(row.get("finding_id"))
            for row in supplemental_rows
            if isinstance(row, Mapping)
        ]
        if len(supplemental_ids) != len(set(supplemental_ids)):
            errors.append("duplicate_supplemental_finding_id")
        expected_dates = {
            row["finding_id"]: row["decision_date"]
            for row in generated_supplemental
        }
        for row in supplemental_rows:
            if not isinstance(row, Mapping):
                continue
            finding_id = str(row.get("finding_id", "unknown"))
            expected_date = expected_dates.get(finding_id)
            if expected_date is not None and row.get("decision_date") != expected_date:
                errors.append(f"supplemental_decision_date_drift:{finding_id}")
    if schema:
        errors.extend(_schema_errors(data, SCHEMA_PATH))
        if any(error.startswith("schema:") for error in errors):
            return errors
    _validate_ds18_time_semantics_coverage(data, errors)
    ds8_coverage = data.get("ds8_strangle_coverage")
    if not isinstance(ds8_coverage, Mapping):
        errors.append("ds8_strangle_coverage_missing")
    else:
        errors.extend(validate_ds8_strangle_coverage(ds8_coverage))
    ds8b_transition = data.get("ds8b_post_freeze_transition")
    if not isinstance(ds8b_transition, Mapping):
        errors.append("ds8b_post_freeze_transition_missing")
    elif isinstance(ds8_coverage, Mapping):
        errors.extend(
            validate_ds8b_post_freeze_transition(
                ds8b_transition,
                ds8_coverage,
            )
        )
    _validate_storage_construction_census(data, errors)
    ds1 = _load_json(DS1_PATH)
    ds2 = _load_json(DS2_PATH)
    ds1_ids = [entry["surface_id"] for entry in ds1["entries"]]
    ds1_by_id = {entry["surface_id"]: entry for entry in ds1["entries"]}
    mapped, unbound, mapping_errors = _ds2_links(set(ds1_ids), ds2)
    errors.extend(mapping_errors)

    if data["sources"]["ds1"]["sha256"] != _sha256(DS1_PATH):
        errors.append("ds1_source_hash_drift")
    if data["sources"]["ds2"]["sha256"] != _sha256(DS2_PATH):
        errors.append("ds2_source_hash_drift")
    if data["sources"]["ds1"]["expected_entries"] != len(ds1_ids):
        errors.append("ds1_source_count_drift")
    if data["sources"]["ds2"]["expected_entries"] != len(ds2["entries"]):
        errors.append("ds2_source_count_drift")

    entries = data["entries"]
    entry_ids = [entry["unit_id"] for entry in entries]
    if entry_ids != ds1_ids:
        missing = sorted(set(ds1_ids) - set(entry_ids))
        extra = sorted(set(entry_ids) - set(ds1_ids))
        errors.append(f"ds1_register_parity:missing={missing}:extra={extra}:order_drift={not missing and not extra}")
    if len(entry_ids) != len(set(entry_ids)):
        errors.append("register_duplicate_unit")
    entry_by_id = {entry["unit_id"]: entry for entry in entries}
    _validate_ds9_c07_adjudication(data, entry_by_id, errors)
    _validate_ds10_capability_discovery_roots(entry_by_id, errors)
    for entry in entries:
        if (
            "aggregate_disposition_receipt" in entry
            and entry["unit_id"] != UI_PRIMITIVES_ROOT_ID
        ):
            errors.append(f"ui_primitives_receipt_wrong_root:{entry['unit_id']}")
    _validate_ui_primitives_mixed_receipt(
        entry_by_id[UI_PRIMITIVES_ROOT_ID], errors
    )

    linked_ds2: list[str] = []
    for unit_id, entry in entry_by_id.items():
        evidence = entry["evidence_link"]
        if evidence["ds1_entry_id"] != unit_id:
            errors.append(f"ds1_identity_mismatch:{unit_id}")
        expected_ds2 = mapped.get(unit_id, [])
        if evidence["ds2_adoption_ids"] != expected_ds2:
            errors.append(f"ds2_links_drift:{unit_id}")
        linked_ds2.extend(evidence["ds2_adoption_ids"])
    if data["ds2_unbound_adoption_ids"] != unbound:
        errors.append("ds2_unbound_drift")
    all_ds2 = [entry["id"] for entry in ds2["entries"]]
    if Counter(linked_ds2 + list(data["ds2_unbound_adoption_ids"])) != Counter(all_ds2):
        errors.append("ds2_link_reconciliation_drift")

    derived_operations = _derived_operation_ids(ds1)
    configured_operations = set(WIRE_OPERATION_RATIONALES) | set(RETIRE_OPERATION_RATIONALES)
    if derived_operations != configured_operations or len(derived_operations) != 37:
        errors.append("uncalled_operation_source_set_drift")
    derived_flags = _derived_flag_ids(ds1)
    if derived_flags != set(FLAG_DECISIONS) or len(derived_flags) != 4:
        errors.append("consumer_missing_flag_source_set_drift")

    for unit_id in derived_operations:
        entry = entry_by_id.get(unit_id)
        expected = "wire_disposition" if unit_id in WIRE_OPERATION_RATIONALES else "retire_disposition"
        if entry is None or entry["disposition"] != expected:
            errors.append(f"uncalled_operation_decision_missing:{unit_id}")
        elif entry["owner_slice"] != "DS3" or entry["decision_detail"]["consumer_slice"] != "DS3":
            errors.append(f"uncalled_operation_consumer_slice_invalid:{unit_id}")
    for unit_id, (expected, _rationale) in FLAG_DECISIONS.items():
        entry = entry_by_id.get(unit_id)
        if entry is None or entry["disposition"] != expected:
            errors.append(f"consumer_missing_flag_decision_missing:{unit_id}")
        elif entry["owner_slice"] != "DS5" or entry["decision_detail"]["consumer_slice"] != "DS5":
            errors.append(f"consumer_missing_flag_consumer_slice_invalid:{unit_id}")

    for unit_id in DELETE_ROOT_IDS:
        entry = entry_by_id.get(unit_id)
        if entry is None or entry["disposition"] not in {"delete_pending", "deleted"}:
            errors.append(f"wave_candidate_disposition_invalid:{unit_id}")
    signing = entry_by_id.get("derivation-browser-signature")
    if signing is None or signing["disposition"] != "rebind_pending" or signing["owner_slice"] != "DS12":
        errors.append("browser_signing_protection_missing")

    censuses = {census["census_id"]: census for census in data["reference_censuses"]}
    if len(censuses) != len(data["reference_censuses"]):
        errors.append("duplicate_census_id")
    _validate_ui_primitives_receipt_semantics(
        entry_by_id[UI_PRIMITIVES_ROOT_ID],
        ds2,
        censuses,
        errors,
        live_probes=live_probes,
    )
    _validate_c15_mixed_receipt(
        entry_by_id[C15_ROOT_ID],
        ds2,
        errors,
        live_probes=live_probes,
    )
    _validate_c16_mixed_receipt(
        entry_by_id[C16_ROOT_ID],
        ds2,
        errors,
        live_probes=live_probes,
    )
    _validate_c17_responsive_receipt(
        entry_by_id[C17_ROOT_ID],
        entry_by_id[C17_TOKEN_ROOT_ID],
        ds2,
        errors,
        live_probes=live_probes,
    )
    _validate_c11b_query_memory_root(entry_by_id, errors)
    _validate_c13_print_export_root(entry_by_id, errors)
    _validate_c23_containment_roots(entry_by_id, errors)
    for unit in [*entries, *data["subunits"]]:
        _validate_composition(unit, censuses, errors)

    if live_probes:
        for census in data["reference_censuses"]:
            for probe in census["probes"]:
                observed = _recompute_probe(probe)
                observation_matches, mode_error = _probe_observation_matches_stored_mode(
                    probe["observed_refs"], observed
                )
                if mode_error:
                    errors.append(
                        f"{mode_error}:{census['census_id']}:{probe['kind']}"
                    )
                elif not observation_matches:
                    errors.append(f"census_observation_drift:{census['census_id']}:{probe['kind']}")
                if len(observed) != probe["expected_count"]:
                    errors.append(f"census_expected_count_drift:{census['census_id']}:{probe['kind']}")

    terminal_ids = {
        unit["unit_id"]
        for unit in [*entries, *data["subunits"]]
        if unit["disposition"] == "deleted"
    }
    for cluster, proof in CLUSTER_PROOFS.items():
        covered = terminal_ids & set(proof["unit_ids"])
        if not covered:
            continue
        matching = [
            census
            for census in data["reference_censuses"]
            if covered <= set(census["covers_unit_ids"])
            and census["result"] == "zero_consumers"
        ]
        if not matching:
            errors.append(f"code_owned_deletion_census_missing:{cluster}")
            continue
        probes = matching[0]["probes"]
        stored_paths = {
            target
            for probe in probes
            if probe["kind"] == "path_absent"
            for target in probe["targets"]
        }
        stored_targets = {
            target
            for probe in probes
            if probe["kind"] in {"reference_count", "typescript_import_census"}
            for target in probe["targets"]
        }
        if not set(proof["paths"]) <= stored_paths:
            errors.append(f"code_owned_path_probe_missing:{cluster}")
        if not set(proof["targets"]) <= stored_targets:
            errors.append(f"code_owned_reference_probe_missing:{cluster}")

    subunit_by_id = {entry["unit_id"]: entry for entry in data["subunits"]}
    ru = subunit_by_id.get("route-app-layout::ru-ui-catalog")
    if (
        ru is None
        or ru["disposition"] != "frozen_legacy_continuity"
        or not _path_from_ref(ru["continuity_guard"]["required_path"]).exists()
    ):
        errors.append("ru_frozen_legacy_missing")
    whatif = subunit_by_id.get("feature-whatif::legacy-local-whatif-subgraph")
    if whatif is None or whatif["parent_ds1_entry_id"] != "feature-whatif":
        errors.append("whatif_dead_subgraph_missing")

    finding_ids = {item["finding_id"] for item in data["supplemental_findings"]}
    if finding_ids != EXPECTED_FINDING_IDS:
        errors.append(f"repair_observation_drift:missing={sorted(EXPECTED_FINDING_IDS-finding_ids)}:extra={sorted(finding_ids-EXPECTED_FINDING_IDS)}")
    if not BASELINE_PATH.exists() or not BASELINE_SCHEMA_PATH.exists():
        errors.append("baseline_debt_manifest_missing")
    else:
        baseline = (
            baseline_manifest
            if baseline_manifest is not None
            else _load_json(BASELINE_PATH)
        )
        errors.extend(
            "baseline_" + error for error in validate_baseline_manifest(baseline)
        )
        findings_by_id = {
            row["finding_id"]: row for row in data["supplemental_findings"]
        }
        active_test_classes = {
            row["class_id"]: row for row in baseline["vitest"]["debt_classes"]
        }
        try:
            c03_lifecycle = _c03_vitest_lifecycle_state(baseline)
        except ValueError:
            c03_lifecycle = "invalid"
        expected_debt_lifecycle = {
            "baseline-lint-quantity-debt": (
                "open_debt" if baseline["lint"]["error_count"] > 0 else "repaired",
                "DS4",
            ),
            "baseline-test-i18n-count-debt": (
                "open_debt" if c03_lifecycle == "open" else "repaired",
                active_test_classes.get(
                    "i18n-count-message-parity", {"owner_slice": "DS6"}
                )["owner_slice"],
            ),
            "baseline-test-a11y-coverage-debt": (
                "open_debt"
                if "shared-ui-a11y-coverage" in active_test_classes
                else "repaired",
                "DS4",
            ),
            "baseline-test-temporal-cursor-debt": (
                "open_debt"
                if "temporal-cursor-canonical-url" in active_test_classes
                else "repaired",
                "DS4",
            ),
        }
        for finding_id, (status, owner_slice) in expected_debt_lifecycle.items():
            finding = findings_by_id.get(finding_id, {})
            if finding.get("status") != status:
                errors.append(f"supplemental_debt_status_drift:{finding_id}")
            if finding.get("owner_slice") != owner_slice:
                errors.append(f"supplemental_debt_owner_drift:{finding_id}")

    expected_negatives = {f"DS1-N{number:03d}" for number in range(1, 24)}
    negative_rows = {row["negative_id"]: row for row in data["seeded_negative_lifecycle"]}
    if set(negative_rows) != expected_negatives:
        errors.append("seeded_negative_parity_drift")
    audit_ids = set(NEGATIVE_ID_RE.findall(AUDIT_PATH.read_text(encoding="utf-8")))
    if audit_ids != expected_negatives:
        errors.append("seeded_negative_source_drift")
    for negative_id, row in negative_rows.items():
        for census_id in row.get("deletion_census_ids", []):
            if census_id not in censuses:
                errors.append(f"seeded_negative_census_missing:{negative_id}:{census_id}")
        if row["lifecycle"] == "obsolete_by_deletion":
            if not row.get("deletion_census_ids"):
                errors.append(f"obsolete_negative_receipt_missing:{negative_id}")
            if any(unit_id not in terminal_ids for unit_id in row["affected_unit_ids"]):
                errors.append(f"obsolete_negative_live_substrate:{negative_id}")
        if row["may_count_as_passing_test"] is not False:
            errors.append(f"seeded_negative_laundered:{negative_id}")
    references = [
        data["sources"]["ds1"]["path"],
        data["sources"]["ds2"]["path"],
        data["sources"]["ds0"]["path"],
        data["baseline_debt_manifest_ref"],
    ]
    references.extend(
        ref
        for finding in data["supplemental_findings"]
        for ref in finding["evidence_refs"]
    )
    references.extend(
        ref
        for census in data["reference_censuses"]
        for probe in census["probes"]
        for ref in probe["observed_refs"]
    )
    references.extend(row["source_ref"] for row in data["seeded_negative_lifecycle"])
    references.extend(
        ref
        for census in data["reference_censuses"]
        for ref in census.get("verification_refs", [])
    )
    for reference in references:
        issue = _reference_resolution_error(reference)
        if issue:
            errors.append(issue)
    errors.extend(_typescript_identity_reference_errors(references))
    errors.extend(_structured_identity_reference_errors(references))
    if report_parity:
        errors.extend(_report_projection_errors(data))
    return errors


def _baseline_corruption_probes(baseline: Mapping[str, Any]) -> list[str]:
    """Prove the immutable-origin lifecycle rejects disappearance and laundering."""
    probes: list[tuple[str, dict[str, Any]]] = []

    vitest_receipt_drift = copy.deepcopy(baseline)
    vitest_receipt_drift["vitest"]["command"] += " --changed"
    probes.append(("vitest-receipt-identity-drift", vitest_receipt_drift))

    vitest_lifecycle_mix = copy.deepcopy(baseline)
    vitest_lifecycle_mix["vitest"]["disposition"] = (
        "resolved"
        if baseline["vitest"]["disposition"] == "rebind_pending"
        else "rebind_pending"
    )
    probes.append(("vitest-lifecycle-state-mix", vitest_lifecycle_mix))

    missing_lint = copy.deepcopy(baseline)
    missing_lint["lint"]["resolutions"].pop()
    probes.append(("lint-missing-resolution", missing_lint))

    overlapping_lint = copy.deepcopy(baseline)
    overlap_resolution = overlapping_lint["lint"]["resolutions"][0]
    active_row = overlap_resolution["origin_identity"]
    active_diagnostic = {
        key: value for key, value in active_row.items() if key != "source_content_sha256"
    }
    overlapping_lint["lint"].update(
        {
            "disposition": "rebind_pending",
            "exit_code": 1,
            "error_count": 1,
            "source_file_count": 1,
            "files": [
                {
                    "path": active_row["path"],
                    "content_sha256": active_row["source_content_sha256"],
                    "diagnostic_count": 1,
                    "rule_counts": [
                        {
                            "rule_id": active_row["rule_id"],
                            "count": 1,
                        }
                    ],
                    "diagnostics": [active_diagnostic],
                }
            ],
            "identity_set_sha256": _canonical_sha256([active_row]),
        }
    )
    overlapping_lint["lint"]["diagnostic_set"]["sha256"] = _canonical_sha256([active_diagnostic])
    probes.append(("lint-active-resolved-overlap", overlapping_lint))

    moved_lint = copy.deepcopy(baseline)
    moved_lint["lint"]["resolutions"][0]["origin_identity"]["line"] += 1
    probes.append(("lint-moved-origin-identity", moved_lint))

    fabricated_ref = copy.deepcopy(baseline)
    fabricated_ref["lint"]["resolutions"][0]["implementation_refs"][0] = (
        "apps/runtime-dashboard/src/fabricated-successor.ts"
    )
    probes.append(("lint-fabricated-successor", fabricated_ref))

    missing_content_binding = copy.deepcopy(baseline)
    missing_content_binding["lint"]["resolution_content_bindings"].pop()
    probes.append(("lint-missing-resolution-content-binding", missing_content_binding))

    laundered_content_role = copy.deepcopy(baseline)
    c07_multi_role_binding = next(
        row
        for row in laundered_content_role["lint"]["resolution_content_bindings"]
        if row["cluster_id"] == "C07" and len(row["roles"]) > 1
    )
    c07_multi_role_binding["roles"] = c07_multi_role_binding["roles"][:-1]
    probes.append(("lint-resolution-content-role-laundering", laundered_content_role))

    c07_semantic_laundering = copy.deepcopy(baseline)
    c07_resolution = next(
        row
        for row in c07_semantic_laundering["lint"]["resolutions"]
        if row["cluster_id"] == "C07"
        and row["classification"] == "quantity_semantics"
    )
    c07_resolution["semantic_kind"] = "non_authority_control"
    probes.append(("lint-c07-semantic-kind-laundering", c07_semantic_laundering))

    c07_marker_only = copy.deepcopy(baseline)
    c07_resolution = next(
        row
        for row in c07_marker_only["lint"]["resolutions"]
        if row["cluster_id"] == "C07"
        and row["classification"] == "quantity_semantics"
    )
    c07_resolution["closure_test_ref"] = (
        "apps/runtime-dashboard/src/shared/charts/chartHardening.test.tsx"
    )
    probes.append(("lint-c07-marker-only-closure", c07_marker_only))

    c08_class_laundering = copy.deepcopy(baseline)
    c08_resolution = next(
        row for row in c08_class_laundering["lint"]["resolutions"] if row["cluster_id"] == "C08"
    )
    c08_resolution["classification"] = "motion_geometry"
    probes.append(("lint-c08-classification-laundering", c08_class_laundering))

    c08_semantic_laundering = copy.deepcopy(baseline)
    c08_resolution = next(
        row for row in c08_semantic_laundering["lint"]["resolutions"] if row["cluster_id"] == "C08"
    )
    c08_resolution["semantic_kind"] = "decision_bearing"
    probes.append(("lint-c08-semantic-kind-laundering", c08_semantic_laundering))

    c08_marker_only = copy.deepcopy(baseline)
    c08_resolution = next(
        row for row in c08_marker_only["lint"]["resolutions"] if row["cluster_id"] == "C08"
    )
    c08_resolution["closure_test_ref"] = (
        "apps/runtime-dashboard/src/shared/lib/domain/nonAuthorityNumeric.test.ts"
    )
    probes.append(("lint-c08-marker-only-closure", c08_marker_only))

    c08_missing_adapter = copy.deepcopy(baseline)
    c08_resolution = next(
        row for row in c08_missing_adapter["lint"]["resolutions"] if row["cluster_id"] == "C08"
    )
    c08_resolution["implementation_refs"] = [
        ref
        for ref in c08_resolution["implementation_refs"]
        if ref != "apps/runtime-dashboard/src/shared/lib/domain/nonAuthorityNumeric.ts"
    ]
    probes.append(("lint-c08-canonical-adapter-removed", c08_missing_adapter))

    empty_without_resolutions = copy.deepcopy(baseline)
    empty_lint = empty_without_resolutions["lint"]
    empty_lint.update(
        {
            "disposition": "resolved",
            "exit_code": 0,
            "error_count": 0,
            "source_file_count": 0,
            "files": [],
            "identity_set_sha256": _canonical_sha256([]),
        }
    )
    empty_lint["diagnostic_set"]["sha256"] = _canonical_sha256([])
    empty_lint["resolutions"].pop()
    probes.append(("lint-empty-active-incomplete-resolutions", empty_without_resolutions))

    missing_architecture = copy.deepcopy(baseline)
    missing_architecture["architecture"]["resolutions"].pop()
    probes.append(("architecture-missing-resolution", missing_architecture))

    c18_classification_laundering = copy.deepcopy(baseline)
    c18_resolution = next(
        row
        for row in c18_classification_laundering["architecture"]["resolutions"]
        if row["cluster_id"] == "C18"
    )
    c18_resolution["classification"] = "shared_dependency_inverted"
    probes.append(
        (
            "architecture-c18-classification-laundering",
            c18_classification_laundering,
        )
    )

    sibling_classification_laundering = copy.deepcopy(baseline)
    sibling_resolution = next(
        row
        for row in sibling_classification_laundering["architecture"]["resolutions"]
        if row["cluster_id"] == "C09"
    )
    sibling_resolution["classification"] = "feature_public_barrel"
    probes.append(
        (
            "architecture-non-c18-classification-laundering",
            sibling_classification_laundering,
        )
    )

    failures: list[str] = []
    for name, mutation in probes:
        if not validate_baseline_manifest(mutation):
            failures.append(name)

    c07_scalar_path = (
        "apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.tsx"
    )
    c07_source = (REPO_ROOT / c07_scalar_path).read_bytes()
    try:
        scalar_start = c07_source.index(b"export function chartQuantityScalarPoint")
        scalar_end = c07_source.index(
            b"\nexport function chartQuantityInterval",
            scalar_start,
        )
    except ValueError:
        corrupted_c07_source = c07_source
    else:
        corrupted_c07_source = (
            c07_source[:scalar_start]
            + b"""export function chartQuantityScalarPoint(
  input: ChartQuantityInput | null | undefined,
): number | null {
  // Retained semantic marker strings: chartQuantityMembers, finitePoint,
  // members.length, members[0]?.point, and input == null.
  return null;
}
"""
            + c07_source[scalar_end:]
        )
    if not validate_baseline_manifest(
        baseline,
        source_bytes_override={c07_scalar_path: corrupted_c07_source},
    ):
        failures.append("lint-c07-scalar-property-removed-markers-retained")
    return failures


def _corruption_probes(data: Mapping[str, Any]) -> list[str]:
    probes: list[tuple[str, dict[str, Any]]] = []

    def corrupt_value(value: Any) -> Any:
        if isinstance(value, list):
            return list(reversed(value)) if len(value) > 1 else []
        if isinstance(value, dict):
            return {"corrupt": True}
        return str(value) + "-corrupt"

    missing_root = copy.deepcopy(data)
    missing_root["entries"].pop()
    probes.append(("missing-root", missing_root))

    fake_ds2 = copy.deepcopy(data)
    fake_ds2["entries"][0]["evidence_link"]["ds2_adoption_ids"].append("fake-ds2")
    probes.append(("fake-ds2", fake_ds2))

    rebound_without_successor = copy.deepcopy(data)
    rebound_without_successor["entries"][0]["disposition"] = "rebind_pending"
    rebound_without_successor["entries"][0]["strangle_status"] = "strangled"
    rebound_without_successor["entries"][0].pop("successor", None)
    probes.append(("rebound-without-successor", rebound_without_successor))

    deleted_without_census = copy.deepcopy(data)
    target = next(entry for entry in deleted_without_census["entries"] if entry["unit_id"] in DELETE_ROOT_IDS)
    target["disposition"] = "deleted"
    target["strangle_status"] = "strangled"
    target.pop("reference_census_id", None)
    probes.append(("deleted-without-census", deleted_without_census))

    missing_ru = copy.deepcopy(data)
    missing_ru["subunits"] = [
        row for row in missing_ru["subunits"] if row["unit_id"] != "route-app-layout::ru-ui-catalog"
    ]
    probes.append(("missing-ru", missing_ru))

    missing_finding = copy.deepcopy(data)
    missing_finding["supplemental_findings"].pop()
    probes.append(("missing-finding", missing_finding))

    c06_row = next(
        row
        for row in data["supplemental_findings"]
        if row["finding_id"] == C06_RENDERED_CONTRAST_FINDING_ID
    )
    for field, value in c06_row.items():
        c06_drift = copy.deepcopy(data)
        stored = next(
            row
            for row in c06_drift["supplemental_findings"]
            if row["finding_id"] == C06_RENDERED_CONTRAST_FINDING_ID
        )
        stored[field] = corrupt_value(value)
        probes.append((f"c06-rendered-contrast-{field}-drift", c06_drift))
    c06_open_regression = copy.deepcopy(data)
    open_row = next(
        row
        for row in c06_open_regression["supplemental_findings"]
        if row["finding_id"] == C06_RENDERED_CONTRAST_FINDING_ID
    )
    open_row["status"] = "open_debt"
    open_row.pop("repair_commit", None)
    probes.append(("c06-rendered-contrast-open-regression", c06_open_regression))
    c06_missing = copy.deepcopy(data)
    c06_missing["supplemental_findings"] = [
        row
        for row in c06_missing["supplemental_findings"]
        if row["finding_id"] != C06_RENDERED_CONTRAST_FINDING_ID
    ]
    probes.append(("c06-rendered-contrast-missing", c06_missing))
    c06_duplicate = copy.deepcopy(data)
    c06_duplicate["supplemental_findings"].append(copy.deepcopy(c06_row))
    probes.append(("c06-rendered-contrast-duplicate", c06_duplicate))

    c13_regressions = {
        "pending": ("strangle_status", "pending"),
        "broad-close": ("disposition", "use_as_is"),
        "owner-transfer": ("owner_slice", "DS6"),
        "rationale": ("rationale", "fabricated"),
    }
    for name, (field, value) in c13_regressions.items():
        mutation = copy.deepcopy(data)
        row = next(
            entry
            for entry in mutation["entries"]
            if entry["unit_id"] == C13_PRINT_ROOT_ID
        )
        row[field] = value
        probes.append((f"c13-print-{name}", mutation))
    c13_missing_successor = copy.deepcopy(data)
    next(
        entry
        for entry in c13_missing_successor["entries"]
        if entry["unit_id"] == C13_PRINT_ROOT_ID
    ).pop("successor", None)
    probes.append(("c13-print-missing-successor", c13_missing_successor))

    missing_negative = copy.deepcopy(data)
    missing_negative["seeded_negative_lifecycle"].pop()
    probes.append(("missing-negative", missing_negative))

    wrong_consumer = copy.deepcopy(data)
    op = next(entry for entry in wrong_consumer["entries"] if entry["unit_id"] in WIRE_OPERATION_RATIONALES)
    op["decision_detail"]["consumer_slice"] = "DS8"
    probes.append(("wrong-consumer-slice", wrong_consumer))

    mixed_count_drift = copy.deepcopy(data)
    primitives = next(
        entry
        for entry in mixed_count_drift["entries"]
        if entry["unit_id"] == UI_PRIMITIVES_ROOT_ID
    )
    primitives["aggregate_disposition_receipt"]["counts"]["retired"] = 2
    probes.append(("ui-primitives-mixed-count-drift", mixed_count_drift))

    mixed_blob_drift = copy.deepcopy(data)
    primitives = next(
        entry
        for entry in mixed_blob_drift["entries"]
        if entry["unit_id"] == UI_PRIMITIVES_ROOT_ID
    )
    primitives["aggregate_disposition_receipt"][
        "pre_deletion_resurrection_anchor"
    ]["files"][0]["git_blob"] = "0" * 40
    probes.append(("ui-primitives-resurrection-blob-drift", mixed_blob_drift))

    c15_rationale_drift = copy.deepcopy(data)
    compounds = next(
        entry
        for entry in c15_rationale_drift["entries"]
        if entry["unit_id"] == C15_ROOT_ID
    )
    compounds["rationale"] = "C15 complete."
    probes.append(("ui-compounds-root-mixed-rationale-drift", c15_rationale_drift))

    c16_rationale_drift = copy.deepcopy(data)
    patterns = next(
        entry
        for entry in c16_rationale_drift["entries"]
        if entry["unit_id"] == C16_ROOT_ID
    )
    patterns["rationale"] = "C16 complete."
    probes.append(("ui-patterns-mixed-rationale-drift", c16_rationale_drift))

    c17_rationale_drift = copy.deepcopy(data)
    responsive = next(
        entry
        for entry in c17_rationale_drift["entries"]
        if entry["unit_id"] == C17_ROOT_ID
    )
    responsive["rationale"] = "C17 proves responsive readiness."
    probes.append(("ui-responsive-use-as-is-rationale-drift", c17_rationale_drift))

    storage_fingerprint_drift = copy.deepcopy(data)
    storage_fingerprint_drift["storage_construction_census"]["sites"][0][
        "source_fingerprint"
    ] = "sha256:" + "0" * 64
    probes.append(
        ("storage-construction-source-fingerprint-drift", storage_fingerprint_drift)
    )

    storage_class_drift = copy.deepcopy(data)
    storage_site = next(
        row
        for row in storage_class_drift["storage_construction_census"]["sites"]
        if row["classification"] == "scoped_authority"
    )
    storage_site["classification"] = "interaction_benign"
    storage_site["benign_reason"] = "ui_preference"
    storage_site.pop("scoped_envelope_owner")
    storage_site.pop("registered_codec_id")
    probes.append(("storage-construction-class-retag", storage_class_drift))

    for finding_id, descriptor in PRODUCER_BINDING_DEBT_DESCRIPTORS.items():
        governed_fields = ("finding_id", *descriptor)
        for field in governed_fields:
            mutation = copy.deepcopy(data)
            row = next(
                item
                for item in mutation["supplemental_findings"]
                if item["finding_id"] == finding_id
            )
            value = row[field]
            row[field] = corrupt_value(value)
            probes.append(
                (f"producer-binding-debt-{finding_id}-{field}", mutation)
            )

    failures: list[str] = []
    ds8_coverage = data.get("ds8_strangle_coverage")
    if isinstance(ds8_coverage, Mapping):
        failures.extend(ds8_strangle_corruption_probes(ds8_coverage))
    else:
        failures.append("ds8-strangle-coverage-missing")
    ds8b_transition = data.get("ds8b_post_freeze_transition")
    if isinstance(ds8b_transition, Mapping) and isinstance(ds8_coverage, Mapping):
        failures.extend(
            ds8b_post_freeze_corruption_probes(
                ds8b_transition,
                ds8_coverage,
            )
        )
    else:
        failures.append("ds8b-post-freeze-transition-missing")
    direct_sources = _typescript_production_sources(RAW_TRANSPORT_SCAN_ROOTS)
    benign_sources = {
        **direct_sources,
        "apps/runtime-dashboard/src/shared/lib/directTransportControl.ts": (
            "const control = { fetch: () => undefined };\nvoid control.fetch();\n"
        ),
    }
    if validate_register(
        data,
        live_probes=False,
        report_parity=False,
        direct_transport_sources=benign_sources,
    ):
        failures.append("raw-transport-benign-member-call-counted")
    for name, sources in (
        (
            "raw-transport-direct-constructor-added",
            {
                **direct_sources,
                "apps/runtime-dashboard/src/shared/lib/directTransportAdded.ts": (
                    'void fetch("/probe");\n'
                ),
            },
        ),
        (
            "raw-transport-direct-constructor-removed",
            {
                path: source.replace(
                    "void fetch(TELEMETRY_ENDPOINT, {", "void send(TELEMETRY_ENDPOINT, {"
                )
                if path == "apps/runtime-dashboard/src/shared/telemetry/pipeline.ts"
                else source
                for path, source in direct_sources.items()
            },
        ),
        (
            "raw-transport-direct-constructor-reclassified",
            {
                path: source.replace("new EventSource(", "new WebSocket(")
                if path == "apps/runtime-dashboard/src/app/realtime/sseTransport.ts"
                else source
                for path, source in direct_sources.items()
            },
        ),
    ):
        if not validate_register(
            data,
            live_probes=False,
            report_parity=False,
            direct_transport_sources=sources,
        ):
            failures.append(name)

    for finding_id, descriptor in INTEGRATE_DEBT_DESCRIPTORS.items():
        for field in descriptor:
            mutation = copy.deepcopy(data)
            row = next(
                item
                for item in mutation["supplemental_findings"]
                if item["finding_id"] == finding_id
            )
            value = row[field]
            row[field] = corrupt_value(value)
            probes.append(
                (f"integrate-contract-debt-{finding_id}-{field}", mutation)
            )

    authority_id = "authority-presentation-prop-control-approval-readiness"
    missing_authority = copy.deepcopy(data)
    missing_authority["supplemental_findings"] = [
        row
        for row in missing_authority["supplemental_findings"]
        if row["finding_id"] != authority_id
    ]
    probes.append(("authority-presentation-row-removal", missing_authority))
    for field in ("owner_slice", "capability_states", "closure_signal"):
        mutation = copy.deepcopy(data)
        row = next(
            item
            for item in mutation["supplemental_findings"]
            if item["finding_id"] == authority_id
        )
        row[field] = corrupt_value(row[field])
        probes.append((f"authority-presentation-{field}-drift", mutation))
    moved_authority_site = copy.deepcopy(data)
    row = next(
        item
        for item in moved_authority_site["supplemental_findings"]
        if item["finding_id"] == authority_id
    )
    row["authority_sink"]["consumer_sites"][0]["site_sha256"] = (
        "sha256:" + "0" * 64
    )
    probes.append(("authority-presentation-site-hash-drift", moved_authority_site))

    duplicate_finding = copy.deepcopy(data)
    duplicate_finding["supplemental_findings"].append(
        copy.deepcopy(duplicate_finding["supplemental_findings"][0])
    )
    probes.append(("duplicate-supplemental-finding", duplicate_finding))

    old_row_restamp = copy.deepcopy(data)
    old_row_restamp["supplemental_findings"][0]["decision_date"] = (
        DS5_C01A_DECISION_DATE
    )
    probes.append(("accepted-history-decision-date-restamp", old_row_restamp))

    new_row_backdate = copy.deepcopy(data)
    row = next(
        item
        for item in new_row_backdate["supplemental_findings"]
        if item["finding_id"] == authority_id
    )
    row["decision_date"] = DECISION_DATE
    probes.append(("authority-presentation-decision-date-backdate", new_row_backdate))

    ds9_root_id = "route-run-governance"
    ds9_missing_root = copy.deepcopy(data)
    ds9_missing_root["entries"] = [
        row for row in ds9_missing_root["entries"] if row["unit_id"] != ds9_root_id
    ]
    probes.append(("ds9-c07-root-removal", ds9_missing_root))

    ds9_scope_swap = copy.deepcopy(data)
    ds9_scope_row = next(row for row in ds9_scope_swap["entries"] if row["unit_id"] == ds9_root_id)
    ds9_scope_row["seed_rule"] = DS9_C07_SCOPE_SEED_RULE["surface_out_of_scope"]
    probes.append(("ds9-c07-scope-swap", ds9_scope_swap))

    ds9_tombstone_erased = copy.deepcopy(data)
    ds9_tombstone = next(
        row for row in ds9_tombstone_erased["entries"] if row["unit_id"] == "cache-review-attention"
    )
    ds9_tombstone["seed_rule"] = DS9_C07_SCOPE_SEED_RULE["in_scope"]
    probes.append(("ds9-c07-tombstone-erased", ds9_tombstone_erased))

    ds9_out_of_scope_owner = copy.deepcopy(data)
    ds9_out_of_scope = next(
        row for row in ds9_out_of_scope_owner["entries"] if row["unit_id"] == "cache-operator-craft"
    )
    ds9_out_of_scope["owner"] = "team-runtime"
    probes.append(("ds9-c07-out-of-scope-owner", ds9_out_of_scope_owner))

    ds9_authority_id = sorted(DS9_C07_AUTHORITY_FINDING_IDS)[0]
    ds9_authority_row = next(
        row for row in data["supplemental_findings"] if row["finding_id"] == ds9_authority_id
    )
    ds9_missing_authority = copy.deepcopy(data)
    ds9_missing_authority["supplemental_findings"] = [
        row
        for row in ds9_missing_authority["supplemental_findings"]
        if row["finding_id"] != ds9_authority_id
    ]
    probes.append(("ds9-c07-authority-removal", ds9_missing_authority))
    ds9_duplicate_authority = copy.deepcopy(data)
    ds9_duplicate_authority["supplemental_findings"].append(copy.deepcopy(ds9_authority_row))
    probes.append(("ds9-c07-authority-duplicate", ds9_duplicate_authority))
    for field, value in (("status", "repaired"), ("owner_slice", "DS12")):
        mutation = copy.deepcopy(data)
        target = next(
            row
            for row in mutation["supplemental_findings"]
            if row["finding_id"] == ds9_authority_id
        )
        target[field] = value
        probes.append((f"ds9-c07-authority-{field}", mutation))

    for name, mutation in probes:
        if not validate_register(mutation, live_probes=False, report_parity=False):
            failures.append(name)

    authority_scan = _authority_presentation_scan()
    register_text = REGISTER_PATH.read_text(encoding="utf-8")
    try:
        candidate_text = _ds9_c07_register_candidate_text(
            register_text,
            scan=authority_scan,
        )
        normalized = (
            json.dumps(
                json.loads(candidate_text),
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        if not _ds9_c07_preservation_errors(register_text, normalized):
            failures.append("ds9-c07-full-register-reserialization")
        storage_start, storage_end, _storage = _json_top_level_object_span(
            candidate_text,
            "storage_construction_census",
        )
        storage_anchor = '"semantic_class_provenance":'
        storage_anchor_count = candidate_text.count(
            storage_anchor,
            storage_start,
            storage_end,
        )
        if storage_anchor_count != 1:
            failures.append("ds9-c07-storage-nontarget-probe-anchor")
        else:
            anchor_end = candidate_text.index(
                storage_anchor,
                storage_start,
                storage_end,
            ) + len(storage_anchor)
            storage_byte_mutation = (
                candidate_text[:anchor_end]
                + " "
                + candidate_text[anchor_end:]
            )
            if not _ds9_c07_preservation_errors(
                register_text,
                storage_byte_mutation,
            ):
                failures.append("ds9-c07-storage-nontarget-byte-drift")
        repeated = _ds9_c07_register_candidate_text(
            candidate_text,
            scan=authority_scan,
        )
        if repeated != candidate_text:
            failures.append("ds9-c07-transition-not-idempotent")
    except (json.JSONDecodeError, OSError, ValueError):
        failures.append("ds9-c07-transition-probe-invalid")

    reclassified = dict(AUTHORITY_BADGE_CLASSIFICATIONS)
    debt_location = next(
        location
        for location, classification in reclassified.items()
        if classification.startswith("debt:")
    )
    reclassified[debt_location] = "benign:interaction_state"
    if not _badge_classification_errors(authority_scan, reclassified):
        failures.append("authority-badge-reclassification")
    unclassified = dict(AUTHORITY_BADGE_CLASSIFICATIONS)
    unclassified.pop(next(iter(unclassified)))
    if not _badge_classification_errors(authority_scan, unclassified):
        failures.append("authority-badge-unclassified-site")

    retained = {
        name
        for name, rule in UI_PRIMITIVES_MEMBER_RULES.items()
        if rule["disposition"] != "retire"
    }
    expected_package_exports = (
        UI_PRIMITIVES_PACKAGE_MIGRATED
        | ATLAS_UI_DEFINE_ONCE_PRIMITIVES
        | ATLAS_UI_SUPPORT_MODULES
        | ATLAS_UI_OTHER_EXPORTS
    )
    unexpected_module_errors = _ui_primitives_source_state_errors(
        existing_paths={
            *(f"apps/runtime-dashboard/src/shared/ui/{name}.tsx" for name in retained),
            *(f"apps/runtime-dashboard/src/shared/ui/{name}.a11y.test.tsx" for name in retained),
            *(
                f"apps/runtime-dashboard/src/shared/ui/{name}.tsx"
                for name in UI_PRIMITIVES_DASHBOARD_REBOUND
            ),
        },
        dashboard_exports=retained | UI_PRIMITIVES_DASHBOARD_REBOUND,
        atlas_exports=expected_package_exports | {"UnexpectedAuthorityOwner"},
        production_consumers=[],
    )
    if not any(
        error.startswith("ui_primitives_package_exports_unexpected:")
        for error in unexpected_module_errors
    ):
        failures.append("ui-primitives-unexpected-support-module")

    c15_consumers = {
        C15_JSON_PREVIEW_ADAPTER: (
            'import { JsonPreview } from "@polisyos/atlas-ui";\n'
            "const localizedPreview = <JsonPreview data={{}} />;\n"
        ),
        "apps/runtime-dashboard/src/features/c15-valid.tsx": (
            'import { VirtualList, VirtualTable } from "@polisyos/atlas-ui";\n'
            "const consumers = <><VirtualList /><VirtualTable /></>;\n"
        ),
        "packages/atlas-ui/src/compounds/owners.tsx": (
            'import { JsonPreview, VirtualList, VirtualTable } from "@polisyos/atlas-ui";\n'
            "const owners = [JsonPreview, VirtualList, VirtualTable];\n"
        ),
        "packages/atlas-ui/tests/compoundComponents.test.tsx": (
            'import { JsonPreview, VirtualList, VirtualTable } from "@polisyos/atlas-ui";\n'
            "const tests = [JsonPreview, VirtualList, VirtualTable];\n"
        ),
    }
    if _c15_migrated_consumer_errors(c15_consumers):
        failures.append("ui-compounds-root-valid-production-consumers")
    unlocalized_consumers = {
        **c15_consumers,
        "apps/runtime-dashboard/src/features/c15-unlocalized.tsx": (
            'import { JsonPreview } from "@polisyos/atlas-ui";\n'
            "const preview = <JsonPreview data={{}} />;\n"
        ),
    }
    if (
        "ui_compounds_root_unlocalized_json_preview_consumer:"
        "apps/runtime-dashboard/src/features/c15-unlocalized.tsx"
        not in _c15_migrated_consumer_errors(unlocalized_consumers)
    ):
        failures.append("ui-compounds-root-unlocalized-json-preview")
    c15_consumers[C15_JSON_PREVIEW_ADAPTER] = (
        'import { JsonPreview } from "@polisyos/atlas-ui";\n'
        "void JsonPreview;\n"
    )
    c15_consumers["apps/runtime-dashboard/src/features/c15-valid.tsx"] = (
        'import { VirtualList, VirtualTable } from "@polisyos/atlas-ui";\n'
        "const markers = [VirtualList, VirtualTable];\n"
    )
    expected_missing_consumers = [
        f"ui_compounds_root_production_consumer_missing:{component}"
        for component in sorted(C15_PACKAGE_MIGRATED)
    ]
    if _c15_migrated_consumer_errors(c15_consumers) != expected_missing_consumers:
        failures.append("ui-compounds-root-production-consumption-removed")

    c16_consumers = {
        "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx": (
            'import { DetailLayout } from "@polisyos/atlas-ui";\n'
            "const layout = <DetailLayout content={null} />;\n"
        ),
        "apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx": (
            'import { FilterPanel } from "@polisyos/atlas-ui";\n'
            'const filters = <FilterPanel title="Filters" />;\n'
        ),
    }
    valid_c16_errors = _c16_pattern_source_state_errors(
        sources=c16_consumers,
        existing_paths=set(C16_REQUIRED_PATHS),
        atlas_exports=set(C16_PACKAGE_MIGRATED),
    )
    if valid_c16_errors:
        failures.append("ui-patterns-valid-mixed-source-state")
    for consumer_path, component in (
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
            path: source
            for path, source in c16_consumers.items()
            if path != consumer_path
        }
        expected_error = f"ui_patterns_production_consumer_missing:{component}"
        if expected_error not in _c16_pattern_source_state_errors(
            sources=reduced_sources,
            existing_paths=set(C16_REQUIRED_PATHS),
            atlas_exports=set(C16_PACKAGE_MIGRATED),
        ):
            failures.append(f"ui-patterns-direct-consumer-removal:{component}")
    promoted_paths = {
        *C16_REQUIRED_PATHS,
        "packages/atlas-ui/src/patterns/SearchableList.tsx",
    }
    if (
        "ui_patterns_searchable_list_promoted_without_consumer"
        not in _c16_pattern_source_state_errors(
            sources=c16_consumers,
            existing_paths=promoted_paths,
            atlas_exports={*C16_PACKAGE_MIGRATED, C16_SEARCHABLE_LIST},
        )
    ):
        failures.append("ui-patterns-searchable-list-consumerless-promotion")
    return failures


def _ds8_strangle_report_projection(coverage: Mapping[str, Any]) -> str:
    """Render the complete DS8 assignment map without sampled path summaries."""
    assignments = list(coverage["assignments"])
    baseline_rows = [row for row in assignments if row["origin"] == "opening_base"]
    lines = [
        "### DS8 case/evidence strangle coverage",
        "",
        (
            f"Predicate provenance: `{coverage['predicate_provenance']}`. "
            f"Family complete: `{str(coverage['family_complete']).lower()}`."
        ),
        "",
        "| Feature | Opening production | In scope | Deferred |",
        "| --- | ---: | ---: | ---: |",
    ]
    totals = Counter()
    for feature in ("runs", "artifacts", "evidence"):
        rows = [
            row
            for row in baseline_rows
            if row["feature"] == feature and row["role"] == "production"
        ]
        in_scope = sum(row["disposition"] == "in_scope" for row in rows)
        deferred = sum(
            row["disposition"] == "surface_out_of_scope" for row in rows
        )
        totals.update(total=len(rows), in_scope=in_scope, deferred=deferred)
        lines.append(f"| {feature} | {len(rows)} | {in_scope} | {deferred} |")
    lines.extend(
        [
            (
                f"| **Total** | **{totals['total']}** | "
                f"**{totals['in_scope']}** | **{totals['deferred']}** |"
            ),
            "",
            (
                f"Opening companions: **{coverage['baseline']['tests']['files']} "
                "tests** and "
                f"**{coverage['baseline']['stories']['files']} stories**. "
                f"Source-freeze additions: **{coverage['new_path_count']} paths**."
            ),
            "",
            (
                f"T0 `{coverage['baseline']['commit']}`: "
                f"`{coverage['baseline']['path_manifest_sha256']}`; source freeze "
                f"`{coverage['source_freeze']['commit']}`: "
                f"`{coverage['source_freeze']['path_manifest_sha256']}`."
            ),
            "",
            "| Closure cluster | Files | Source commit | Path/content receipt |",
            "| --- | ---: | --- | --- |",
        ]
    )
    for receipt in coverage["closure_receipts"]:
        lines.append(
            f"| `{receipt['cluster']}` | {receipt['file_count']} | "
            f"`{receipt['source_commit']}` | "
            f"`{receipt['path_content_manifest_sha256']}` |"
        )
    lines.extend(
        [
            "",
            "#### Complete DS8 path projection",
            "",
            "| Path | Feature | Role | Origin | Disposition | Closure | Owner / exit |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in assignments:
        closure = row.get("closure_cluster", "—")
        owner = (
            f"`{row['owner_team']}` / `{row['capability_state']}` / "
            f"`{row['exit_condition']}` / successor `null`"
            if row["disposition"] == "surface_out_of_scope"
            else "—"
        )
        lines.append(
            f"| `{row['path']}` | `{row['feature']}` | `{row['role']}` | "
            f"`{row['origin']}` | `{row['disposition']}` | `{closure}` | "
            f"{owner} |"
        )
    return "\n".join(lines)


def _ds8b_transition_report_projection(
    transition: Mapping[str, Any],
) -> str:
    """Render every row in DS8-B's separately frozen post-C07 transition."""
    historical = transition["historical_binding"]
    lines = [
        "### DS8-B post-freeze transition",
        "",
        (
            f"Predicate provenance: `{transition['predicate_provenance']}`. "
            f"Transition complete: "
            f"`{str(transition['transition_complete']).lower()}`."
        ),
        "",
        (
            f"Historical map preserved: **{historical['assignment_count']} rows** "
            f"including **{historical['deferred_count']} deferrals**, bound by "
            f"`{historical['coverage_sha256']}`."
        ),
        "",
        (
            f"Immutable base `{transition['baseline']['commit']}` to source freeze "
            f"`{transition['source_freeze']['commit']}`: "
            f"**{transition['changed_existing_path_count']} changed existing + "
            f"{transition['new_path_count']} new = "
            f"{transition['transition_path_count']} transition rows**."
        ),
        "",
        "| Path | Feature | Role | Origin | Disposition | Source bytes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in transition["assignments"]:
        lines.append(
            f"| `{row['path']}` | `{row['feature']}` | `{row['role']}` | "
            f"`{row['origin']}` | `{row['disposition']}` | "
            f"`{row['source_content_sha256']}` |"
        )
    return "\n".join(lines)


def _ds9_c07_report_projection(data: Mapping[str, Any]) -> str:
    """Render all 18 adjudicated objects without implying family completion."""
    entries = {row["unit_id"]: row for row in data["entries"]}
    findings = {row["finding_id"]: row for row in data["supplemental_findings"]}
    lines = [
        "### DS9 C07 human-decision adjudication",
        "",
        "Predicate provenance: `independently_reconciled`. Family complete: `false`.",
        "",
        "| Object | Kind | DS9 semantic scope | Formal disposition | Owner / residual |",
        "| --- | --- | --- | --- | --- |",
    ]
    for unit_id, scope in DS9_C07_ROOT_SCOPE.items():
        row = entries[unit_id]
        lines.append(
            f"| `{unit_id}` | root | `{scope}` | `{row['disposition']}` / "
            f"`{row['strangle_status']}` | `{row['owner_slice']}` |"
        )
    for finding_id in sorted(DS9_C07_AUTHORITY_FINDING_IDS):
        row = findings[finding_id]
        states = ", ".join(f"`{state}`" for state in row["capability_states"])
        lines.append(
            f"| `{finding_id}` | authority support | `in_scope` | "
            f"`{row['disposition']}` / `{row['status']}` | "
            f"`{row['owner_slice']}`; {states} |"
        )
    return "\n".join(lines)


def _report_projection(data: Mapping[str, Any]) -> str:
    entries = data["entries"]
    censuses = {row["census_id"]: row for row in data["reference_censuses"]}
    lines = [
        "### Register statistics",
        "",
        "| Disposition | Root units |",
        "| --- | ---: |",
    ]
    for disposition, count in sorted(Counter(row["disposition"] for row in entries).items()):
        lines.append(f"| `{disposition}` | {count} |")
    lines.extend(
        [
            "| **Total DS1 roots** | **261** |",
            "",
            "DS2 evidence reconciliation: **233 = 173 mapped + 60 unbound**. DS2 rows are evidence edges, not 233 additional estate owners.",
            "",
            "### Deletion wave",
            "",
            "| Cluster | Units | Census result | Disposition | Verification |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    entry_by_id = {row["unit_id"]: row for row in entries}
    subunit_by_id = {row["unit_id"]: row for row in data["subunits"]}
    for cluster, proof in CLUSTER_PROOFS.items():
        unit_ids = sorted(proof["unit_ids"])
        rows = [entry_by_id.get(unit_id) or subunit_by_id.get(unit_id) for unit_id in unit_ids]
        rows = [row for row in rows if row is not None]
        disposition = "deleted" if rows and all(row["disposition"] == "deleted" for row in rows) else "pending"
        census_ids = sorted({row.get("reference_census_id", "") for row in rows} - {""})
        census_results = sorted({censuses[census_id]["result"] for census_id in census_ids if census_id in censuses})
        verification_refs = sorted(
            {
                ref
                for census_id in census_ids
                for ref in censuses.get(census_id, {}).get("verification_refs", [])
            }
        )
        lines.append(
            "| "
            + cluster
            + " | "
            + ", ".join(f"`{unit_id}`" for unit_id in unit_ids)
            + " | "
            + (", ".join(census_results) if census_results else "not yet captured")
            + " | `"
            + disposition
            + "` | "
            + (", ".join(f"`{ref}`" for ref in verification_refs) if verification_refs else "pending")
            + " |"
        )

    primitive_entry = entry_by_id[UI_PRIMITIVES_ROOT_ID]
    primitive_receipt = primitive_entry.get("aggregate_disposition_receipt")
    if primitive_receipt is not None:
        counts = primitive_receipt["counts"]
        lines.extend(
            [
                "",
                "### DS4 primitive aggregate disposition",
                "",
                "| Outcome | Count |",
                "| --- | ---: |",
                f"| Package migrated | {counts['package_migrated']} |",
                f"| Dashboard rebound | {counts['dashboard_rebound']} |",
                f"| Retired | {counts['retired']} |",
                f"| Use as-is | {counts['use_as_is']} |",
                f"| **Total** | **{counts['total']}** |",
                "",
                "| Dormant primitive | Disposition | DS2 adoption row | Governing condition |",
                "| --- | --- | --- | --- |",
            ]
        )
        for member in primitive_receipt["c03b_members"]:
            adoption_id = member["ds2_adoption_id"] or "none"
            condition = (
                member["governing_condition"]
                or "No exact DS2 row; retirement is not prohibited."
            )
            lines.append(
                f"| `{member['primitive']}` | `{member['disposition']}` | "
                f"`{adoption_id}` | {condition} |"
            )
        anchor = primitive_receipt["pre_deletion_resurrection_anchor"]
        lines.extend(
            [
                "",
                f"Pre-deletion resurrection commit: `{anchor['git_commit']}`.",
                "",
                "Resurrection rule: "
                f"`{primitive_receipt['resurrection_rule']}`.",
            ]
        )

    lines.extend(
        [
            "",
            "### Wire dispositions — 13 OpenAPI operations",
            "",
            "| Unit | Consumer slice | Rationale |",
            "| --- | --- | --- |",
        ]
    )
    for unit_id in sorted(WIRE_OPERATION_RATIONALES):
        row = entry_by_id[unit_id]
        lines.append(
            f"| `{unit_id}` | `{row['decision_detail']['consumer_slice']}` | {row['decision_detail']['rationale']} |"
        )
    lines.extend(
        [
            "",
            "### Retire dispositions — 24 OpenAPI operations",
            "",
            "Retirement is from frontend adoption only; no endpoint is removed by DS19.",
            "",
            "| Unit | Consumer slice | Rationale |",
            "| --- | --- | --- |",
        ]
    )
    for unit_id in sorted(RETIRE_OPERATION_RATIONALES):
        row = entry_by_id[unit_id]
        lines.append(
            f"| `{unit_id}` | `{row['decision_detail']['consumer_slice']}` | {row['decision_detail']['rationale']} |"
        )
    lines.extend(
        [
            "",
            "### Consumer-missing flag dispositions",
            "",
            "| Unit | Decision | Consumer slice | Rationale |",
            "| --- | --- | --- | --- |",
        ]
    )
    for unit_id in sorted(FLAG_DECISIONS):
        row = entry_by_id[unit_id]
        lines.append(
            f"| `{unit_id}` | `{row['disposition']}` | `{row['decision_detail']['consumer_slice']}` | {row['decision_detail']['rationale']} |"
        )

    persistence_census = data["storage_construction_census"]
    persistence_sites = persistence_census["sites"]
    persistence_counts = Counter(row["classification"] for row in persistence_sites)
    lines.extend(
        [
            "",
            "### Persistence construction census",
            "",
            (
                f"Declaration-resolved production denominator: "
                f"**{persistence_census['production_source_count']} TS/TSX sources**, "
                f"**{persistence_census['site_count']} sites / "
                f"{persistence_census['production_file_count']} files**. "
                f"Classes: **{persistence_counts['scoped_authority']} scoped authority**, "
                f"**{persistence_counts['interaction_benign']} interaction benign**, "
                f"**{persistence_counts['rollout_cache_pending']} rollout cache pending**; "
                f"**{persistence_census['authority_factory_count']} independently "
                "content-bound authority factory declarations**. Direct construction "
                f"facts are `{persistence_census['direct_construction_provenance']}`; "
                "semantic classes are "
                f"`{persistence_census['semantic_class_provenance']}`; exact "
                "site-to-owner-instance flow is "
                f"`{persistence_census['authority_flow_provenance']}`."
            ),
            "",
            (
                "Declared bounded residual: "
                f"{persistence_census['authority_flow_scope']}. Falsifier: "
                f"`{persistence_census['authority_flow_falsifier']}`. Closing it "
                "requires "
                f"{persistence_census['authority_flow_required_capability']}; "
                "repository capability status: "
                f"`{persistence_census['authority_flow_capability_status']}`."
            ),
            "",
            "| Site | Declared adjudication | Resolved API / operation | Store owner | Source | Fingerprints | Posture |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in persistence_sites:
        if row["classification"] == "scoped_authority":
            posture = (
                f"`{row['scoped_envelope_owner']}` / "
                f"`{row['registered_codec_id']}`; "
                "authority flow `not_established`"
            )
        elif row["classification"] == "interaction_benign":
            posture = f"`{row['benign_reason']}`"
        else:
            states = ", ".join(
                f"`{state}`" for state in row["capability_states"]
            )
            posture = (
                f"`{row['owner_slice']}`; {states}; {row['closure_signal']}"
            )
        lines.append(
            f"| `{row['site_id']}` | `{row['classification']}` | "
            f"`{row['resolved_api_declaration']}` / `{row['operation']}` | "
            f"`{row['store_owner']}` | `{row['path']}` | "
            f"`{row['source_fingerprint'][7:19]}` / "
            f"`{row['site_fingerprint'][7:19]}` | {posture} |"
        )

    lines.extend(
        [
            "",
            "### Subunits and structural findings",
            "",
            "| ID | Kind | Disposition | Owner slice/team | Capability states | "
            "Closure signal | State/reason |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in data["subunits"]:
        lines.append(
            f"| `{row['unit_id']}` | `{row['scope_kind']}` | `{row['disposition']}` | `{row['owner_slice']}` | — | — | {row['rationale']} |"
        )
    for row in data["supplemental_findings"]:
        capability_states = row.get("capability_states")
        capability_projection = (
            ", ".join(f"`{state}`" for state in capability_states)
            if capability_states
            else "—"
        )
        closure_projection = row.get("closure_signal", "—")
        owner_projection = row.get("owner_team", row["owner_slice"])
        lines.append(
            f"| `{row['finding_id']}` | `{row['finding_kind']}` | "
            f"`{row['disposition']}` | `{owner_projection}` | "
            f"{capability_projection} | {closure_projection} | "
            f"`{row['status']}` — {row['rationale']} |"
        )

    lines.extend(
        [
            "",
            "### Seeded-negative lifecycle",
            "",
            "| Negative | Lifecycle | Affected units | Deletion census |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in data["seeded_negative_lifecycle"]:
        lines.append(
            f"| `{row['negative_id']}` | `{row['lifecycle']}` | "
            + (", ".join(f"`{unit_id}`" for unit_id in row["affected_unit_ids"]) or "—")
            + " | "
            + (", ".join(f"`{census_id}`" for census_id in row.get("deletion_census_ids", [])) or "—")
            + " |"
        )

    lines.extend(
        [
            "",
            "### Complete DS1-root projection",
            "",
            "| Unit | DS1 evidence | DS2 evidence count | Disposition | Strangle | Owner slice | Census/successor |",
            "| --- | --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for row in entries:
        terminal = row.get("reference_census_id") or (
            row.get("successor", {}).get("unit_id") if row.get("successor") else "—"
        )
        lines.append(
            f"| `{row['unit_id']}` | `{row['evidence_link']['ds1_entry_id']}` | {len(row['evidence_link']['ds2_adoption_ids'])} | `{row['disposition']}` | `{row['strangle_status']}` | `{row['owner_slice']}` | `{terminal}` |"
        )
    lines.extend(
        [
            "",
            _ds9_c07_report_projection(data),
            "",
            _ds8_strangle_report_projection(data["ds8_strangle_coverage"]),
            "",
            _ds8b_transition_report_projection(
                data["ds8b_post_freeze_transition"]
            ),
        ]
    )
    return "\n".join(lines)


def _application_reduction() -> tuple[int, int, int]:
    numstat = subprocess.run(
        ["git", "diff", "--numstat", REPAIR_COMMIT, "--", "policy-engine/apps/runtime-dashboard"],
        cwd=REPO_ROOT.parent,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    added = deleted = 0
    for line in numstat.splitlines():
        added_text, deleted_text, _path = line.split("\t", 2)
        if added_text.isdigit():
            added += int(added_text)
        if deleted_text.isdigit():
            deleted += int(deleted_text)
    deleted_files = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=D",
            REPAIR_COMMIT,
            "--",
            "policy-engine/apps/runtime-dashboard",
        ],
        cwd=REPO_ROOT.parent,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return added, deleted, len(deleted_files)


def _recent_commits() -> list[str]:
    output = subprocess.run(
        ["git", "log", "--format=%h %s", f"{REPAIR_COMMIT}^..HEAD"],
        cwd=REPO_ROOT.parent,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return output.splitlines()


def render_report(data: Mapping[str, Any]) -> str:
    """Render the human report with an exact register-derived projection."""
    baseline = _load_json(BASELINE_PATH)
    added, deleted, deleted_files = _application_reduction()
    projection = _report_projection(data)
    census_count = len(data["reference_censuses"])
    commit_lines = "\n".join(f"- `{line}`" for line in _recent_commits())
    return f"""# Atlas DS19 Frontend Disposition Register and Strangle-Wave Report

Status: `implementation_complete_no_merge_baseline_red`; architect review
pending; generated register projection and human verification receipts.

This report projects the typed register. It does not replace DS1/DS2 evidence,
upgrade readiness, or authorize a pending deletion/rebind. The block between
the projection markers is regenerated and exact-compared by the standalone
checker.

## Baseline toolchain receipts

| Gate | Before result | Acceptance law |
| --- | --- | --- |
| Typecheck | PASS, 11.63 s | absolute green |
| Production build + PWA + security | PASS, 22.69 s; 3,880 modules; 102 precache entries | absolute green |
| ESLint | 75 errors, 0 warnings; initial enumeration about 19 min; cached JSON 5.93 s | current diagnostic multiset must be a subset of manifest `{baseline['manifest_id']}` |
| Vitest | 231 files / 678 tests in 181.12 s; 3 files / 5 tests failed | failed-test identity/signature set must be a subset of the parent-reproduced manifest |

Vitest's same five failures reproduced on parent `7b6933770` in 1.96 s. The
baseline repair is `d01eaa572`; the lockfile changed declarations/importer
edges only, with no version movement. Before lock SHA-256:
`d7fb70700c7934771839730af1697fb6be9958b12fdb4a9cdc78d27f4f0ac309`;
after: `111454fc3a69d075418dd93b5afd787fb13ca551511936eb629f9a09e7fe9eed`.

| Repaired declaration | Resolved before | Resolved after | Graph movement |
| --- | --- | --- | --- |
| `axe-core` | `4.11.4` | `4.11.4` | none |
| `intl-messageformat` | `10.7.18` | `10.7.18` | none |
| `workbox-core` | `7.4.0` | `7.4.0` | none |
| `workbox-precaching` | `7.4.0` | `7.4.0` | none |
| `workbox-routing` | `7.4.0` | `7.4.0` | none |
| `workbox-window` (PWA peer) | `7.4.0` | `7.4.0` | none |

The lockfile diff is confined to the dashboard importer/declaration region;
the package-resolution suffix is byte-identical. No package was introduced and
no version moved.

Audience drift classification: the generated
`PolicyDesignCaseProjection.audience` field landed in `da54f58206` on
2026-05-30; the narrow validator fixture helper predated it in `5c4823ee7` on
2026-05-21. The two negative fixture literals were the only authored
projection literals lagging the generated type. Commit `d01eaa572` made those
fixtures consume the generated audience type; generated and runtime code were
not changed.

## Wave reduction measured from the repaired baseline

- Application lines added: **{added}**
- Application lines deleted: **{deleted}**
- Net application LOC reduction: **{deleted - added}**
- Application files deleted: **{deleted_files}**

## Wave-end full verification

| Gate | Wave-end result | Law |
| --- | --- | --- |
| Typecheck | PASS, 33.98 s | absolute green |
| Production build + PWA + security | PASS, 12.66 s; 3,871 modules; 101 precache entries | absolute green; run after the explicit typecheck because a duplicate-typecheck wrapper attempt was host-memory-killed before Vite |
| ESLint | 916 files; inherited 75 errors / 0 warnings in 5.94 s | zero new diagnostic identities; baseline subset PASS |
| Vitest | 228 files / 664 tests in four deterministic batches; 225 files / 659 tests passed; inherited 3 files / 5 tests failed | failed identity/signature baseline subset PASS |
| Register/check | schema, fresh live probes, report parity, source-byte binding, lint/test comparisons, corruption probes PASS | disposition law enforced |

The monolithic Vitest JSON reporter was host-memory-killed before producing a
receipt, so the complete default-config suite was rerun in four two-worker
batches and mechanically merged. ESLint receipt SHA-256:
`22aed9b244038d5e1c0ed0453a7928ad5917dce229f8ee0de823d203ecb9bebb`;
Vitest receipt SHA-256:
`9046b0d0abd603a2919fda35f2dba0698fa92c158ed3eee62b6fbac6b07d2545`.

## Closure verification

| Gate | Closure result | Interpretation |
| --- | --- | --- |
| Typecheck | PASS, 57.65 s | absolute green |
| Production build + PWA + security | PASS, 28.72 s; 3,871 modules; 101 precache entries | absolute green after the separately recorded typecheck |
| ESLint | 916 files; inherited 75 errors / 0 warnings in 5.96 s | zero new diagnostic identities; baseline subset PASS |
| Vitest | 228 files / 664 tests in 236.92 s; 225 files / 659 tests passed; inherited 3 files / 5 tests failed | failed identity/signature baseline subset PASS |
| Dashboard architecture | 36 inherited violations; 0 violation files changed since `d01eaa572` | baseline-red, no regression; no fence expansion |
| Repository guardrails | PASS, 27.05 s under `uv run --isolated` | default worktree `.venv` is invalid; isolated run installed 116 ephemeral packages and changed no repository file |
| Register/check | schema, 261 DS1 roots, 233 DS2 edges, {census_count} live censuses, report parity, links, source hashes, and corruption probes PASS | disposition authority current |
| Fence | 55 paths, 0 violations against `main...HEAD`; `git diff --check` PASS | DS19 fence only |

Closure ESLint receipt SHA-256:
`22aed9b244038d5e1c0ed0453a7928ad5917dce229f8ee0de823d203ecb9bebb`;
closure Vitest receipt SHA-256:
`21a0ab369f7447ab6a69f93de474cc0b34562e3c33a92a3ba159e254aa163dcb`.
The optional focused counterfactual Playwright journey did not execute because
the fixture server hit the invalid default `.venv` before browser startup;
affected Vitest suites passed, and this non-receipt is not presented as green.

The exact terminal state is
`implementation_complete_no_merge_baseline_red`: reviewable but not merge
ready while inherited lint, Vitest, and dashboard architecture debt remains.
No merge or push is performed.

{REPORT_PROJECTION_START}
{projection}
{REPORT_PROJECTION_END}

## Commits

{commit_lines}

The final documentation/report commit cannot self-record its own hash. The
architect review handoff includes that hash separately. No merge is performed.
"""


def _report_projection_errors(data: Mapping[str, Any]) -> list[str]:
    if not REPORT_PATH.exists():
        return ["report_missing"]
    text = REPORT_PATH.read_text(encoding="utf-8")
    if text.count(REPORT_PROJECTION_START) != 1 or text.count(REPORT_PROJECTION_END) != 1:
        return ["report_projection_markers_invalid"]
    stored = text.split(REPORT_PROJECTION_START, 1)[1].split(REPORT_PROJECTION_END, 1)[0].strip()
    expected = _report_projection(data).strip()
    return [] if stored == expected else ["report_projection_drift"]


def _summary(data: Mapping[str, Any]) -> dict[str, Any]:
    persistence = data["storage_construction_census"]
    ds8 = data["ds8_strangle_coverage"]
    ds8b = data["ds8b_post_freeze_transition"]
    ds18 = data["ds18_time_semantics_coverage"]
    dispositions = Counter(row["disposition"] for row in ds8["assignments"])
    return {
        "root_entries": len(data["entries"]),
        "root_dispositions": dict(sorted(Counter(entry["disposition"] for entry in data["entries"]).items())),
        "subunit_dispositions": dict(sorted(Counter(entry["disposition"] for entry in data["subunits"]).items())),
        "censuses": len(data["reference_censuses"]),
        "supplemental_findings": len(data["supplemental_findings"]),
        "seeded_negatives": len(data["seeded_negative_lifecycle"]),
        "storage_construction_classes": dict(
            sorted(Counter(row["classification"] for row in persistence["sites"]).items())
        ),
        "storage_construction_files": persistence["production_file_count"],
        "storage_construction_sites": persistence["site_count"],
        "storage_production_sources": persistence["production_source_count"],
        "ds8_strangle_assignments": len(ds8["assignments"]),
        "ds8_strangle_dispositions": dict(sorted(dispositions.items())),
        "ds8_strangle_family_complete": ds8["family_complete"],
        "ds8b_transition_assignments": len(ds8b["assignments"]),
        "ds8b_transition_complete": ds8b["transition_complete"],
        "ds18_time_semantics_files": ds18["source_file_count"],
        "ds18_time_semantics_roots": ds18["root_count"],
        "ds18_time_semantics_obligated_roots": ds18["obligated_root_count"],
        "ds18_time_semantics_covered_roots": ds18["covered_root_count"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate the committed register")
    parser.add_argument(
        "--check-ds11-trust-presentation-lock",
        action="store_true",
        help="run the whole register check while holding the DS11 C04 family lock",
    )
    parser.add_argument("--write-seed", action="store_true", help="write a fresh deterministic seed register")
    parser.add_argument(
        "--write-supplemental",
        action="store_true",
        help="refresh only descriptor-derived supplemental findings in the evolved register",
    )
    parser.add_argument(
        "--write-c03-vitest-resolution",
        action="store_true",
        help="surgically transition the exact C03 Vitest receipt to C16 resolved",
    )
    parser.add_argument(
        "--write-c06-rendered-contrast-resolution",
        action="store_true",
        help="surgically transition the exact C04 row from the landed C16 receipt",
    )
    parser.add_argument(
        "--write-c11b-query-memory-root",
        action="store_true",
        help="surgically produce the exact C11b query-memory root transition",
    )
    parser.add_argument(
        "--write-c13-adjacent-print-export-resolution",
        action="store_true",
        help="atomically close the independently verified C13 print predecessor",
    )
    parser.add_argument(
        "--write-ds8-strangle-coverage",
        action="store_true",
        help="atomically materialize the DS8 coverage/register/report/status family",
    )
    parser.add_argument(
        "--write-ds8b-post-freeze-transition",
        action="store_true",
        help="atomically add DS8-B coverage without rewriting C07 history",
    )
    parser.add_argument(
        "--write-ds9-human-decision-integrity",
        action="store_true",
        help="atomically adjudicate the exact DS9 C07 register family",
    )
    parser.add_argument(
        "--write-ds10-capability-discovery",
        action="store_true",
        help="surgically adjudicate the exact ten DS10 capability-discovery roots",
    )
    parser.add_argument(
        "--write-ds11-trust-presentation-resolution",
        action="store_true",
        help="atomically repair only the two DS11 Trust View authority rows and report",
    )
    parser.add_argument(
        "--write-ds18-time-semantics-coverage",
        action="store_true",
        help="materialize the complete DS18 production file/root reconciliation",
    )
    parser.add_argument(
        "--check-ds18-time-semantics-coverage",
        action="store_true",
        help="recompute only the DS18 file/root denominator and semantic receipts",
    )
    parser.add_argument(
        "--write-ds15-acquisition-routes",
        action="store_true",
        help="atomically admit the bounded DS15 query/disposition transition",
    )
    parser.add_argument(
        "--migrate-c21b",
        action="store_true",
        help="surgically migrate gated TypeScript reference strings to C21a identities",
    )
    parser.add_argument(
        "--migrate-c21c",
        action="store_true",
        help="surgically migrate gated JSON/TOML lines to selector identities",
    )
    parser.add_argument(
        "--print-c21b-authority-partition-hashes",
        action="store_true",
        help="print live C21b authority partition-hash derivations without writing",
    )
    parser.add_argument(
        "--print-c21b-authority-identity-literals",
        action="store_true",
        help="print no-write C21b authority identity maps for static freezing",
    )
    parser.add_argument(
        "--print-c21b-descriptor-identities",
        action="store_true",
        help="print no-write full C21a literals for the 15 descriptor bindings",
    )
    parser.add_argument("--write-report", action="store_true", help="regenerate the report projection")
    parser.add_argument("--corruption-probes", action="store_true", help="prove decisive mutations are rejected")
    parser.add_argument(
        "--verify-baseline-source-bytes",
        action="store_true",
        help="prove the captured lint source bytes still equal the before manifest",
    )
    parser.add_argument(
        "--lint-results",
        type=Path,
        help="compare an ESLint JSON result against the baseline diagnostic multiset",
    )
    parser.add_argument(
        "--vitest-results",
        type=Path,
        help="compare a Vitest JSON result against the baseline failed-test set",
    )
    parser.add_argument(
        "--architecture-results",
        type=Path,
        help="compare custom architecture JSON against the active debt set",
    )
    args = parser.parse_args(argv)

    if args.check_ds18_time_semantics_coverage:
        selected = {
            name
            for name, value in vars(args).items()
            if value is not None and value is not False
        }
        if selected != {"check_ds18_time_semantics_coverage"}:
            sys.stderr.write(
                "DS18 time-semantics check requires only "
                "--check-ds18-time-semantics-coverage\n"
            )
            return 1
        try:
            data = _load_json(REGISTER_PATH)
            errors: list[str] = []
            _validate_ds18_time_semantics_coverage(data, errors)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"DS18 time-semantics check rejected: {exc}\n")
            return 1
        if errors:
            for error in errors:
                sys.stderr.write(error + "\n")
            return 1
        coverage = data["ds18_time_semantics_coverage"]
        sys.stdout.write(
            json.dumps(
                {
                    "predicate_provenance": coverage[
                        "predicate_provenance"
                    ],
                    "source_file_count": coverage["source_file_count"],
                    "root_count": coverage["root_count"],
                    "obligated_root_count": coverage["obligated_root_count"],
                    "covered_root_count": coverage["covered_root_count"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return 0

    if args.write_ds18_time_semantics_coverage:
        selected = {
            name
            for name, value in vars(args).items()
            if value is not None and value is not False
        }
        if selected != {"write_ds18_time_semantics_coverage"}:
            sys.stderr.write(
                "DS18 time-semantics writer requires only "
                "--write-ds18-time-semantics-coverage\n"
            )
            return 1
        try:
            opening = _load_json(REGISTER_PATH)
            coverage = _build_ds18_time_semantics_coverage(
                _ds18_time_semantics_scan()
            )
            candidate: dict[str, Any] = {}
            for key, value in opening.items():
                if key == "seeded_negative_lifecycle":
                    candidate["ds18_time_semantics_coverage"] = coverage
                if key != "ds18_time_semantics_coverage":
                    candidate[key] = value
            candidate_errors = _schema_errors(candidate, SCHEMA_PATH)
            _validate_ds18_time_semantics_coverage(
                candidate,
                candidate_errors,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"DS18 time-semantics writer rejected: {exc}\n")
            return 1
        if candidate_errors:
            for error in candidate_errors:
                sys.stderr.write(f"DS18 time-semantics writer rejected: {error}\n")
            return 1
        REGISTER_PATH.write_text(
            json.dumps(candidate, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        sys.stdout.write(
            json.dumps(
                {
                    "files": coverage["source_file_count"],
                    "roots": coverage["root_count"],
                    "obligated_roots": coverage["obligated_root_count"],
                    "covered_roots": coverage["covered_root_count"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return 0

    if args.check_ds11_trust_presentation_lock:
        selected = {
            name
            for name, value in vars(args).items()
            if value is not None and value is not False
        }
        if selected != {"check", "check_ds11_trust_presentation_lock"}:
            sys.stderr.write(
                "DS11 C04 locked check requires only --check "
                "--check-ds11-trust-presentation-lock\n"
            )
            return 1
        try:
            with _ds11_trust_presentation_register_lock():
                completed = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), "--check"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
        except (OSError, ValueError) as exc:
            sys.stderr.write(f"DS11 C04 locked check rejected: {exc}\n")
            return 1
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        return completed.returncode

    if args.write_ds15_acquisition_routes:
        selected = {
            name
            for name, value in vars(args).items()
            if value is not None and value is not False
        }
        if selected != {"write_ds15_acquisition_routes"}:
            sys.stderr.write(
                "DS15 transition requires only --write-ds15-acquisition-routes\n"
            )
            return 1
        try:
            summary = _write_ds15_acquisition_routes_family()
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            sys.stderr.write(f"DS15 transition rejected: {exc}\n")
            return 1
        sys.stdout.write("materialized DS15 register/report transition\n")
        sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return 0

    if args.write_ds11_trust_presentation_resolution:
        selected = {
            name
            for name, value in vars(args).items()
            if value is not None and value is not False
        }
        if selected != {"write_ds11_trust_presentation_resolution"}:
            sys.stderr.write(
                "DS11 C04 transition requires only "
                "--write-ds11-trust-presentation-resolution\n"
            )
            return 1
        try:
            summary = _write_ds11_trust_presentation_family()
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"DS11 C04 transition rejected: {exc}\n")
            return 1
        sys.stdout.write("materialized DS11 C04 two-row register/report transition\n")
        sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return 0

    if args.write_ds10_capability_discovery:
        selected = {
            name
            for name, value in vars(args).items()
            if value is not None and value is not False
        }
        if selected != {"write_ds10_capability_discovery"}:
            sys.stderr.write("DS10 transition requires only --write-ds10-capability-discovery\n")
            return 1
        try:
            summary = _write_ds10_capability_discovery_family()
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            sys.stderr.write(f"DS10 transition rejected: {exc}\n")
            return 1
        sys.stdout.write("materialized DS10 capability-discovery register/report family\n")
        sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return 0

    if args.write_ds9_human_decision_integrity:
        selected = {
            name for name, value in vars(args).items() if value is not None and value is not False
        }
        if selected != {"write_ds9_human_decision_integrity"}:
            sys.stderr.write(
                "DS9 C07 transition requires only --write-ds9-human-decision-integrity\n"
            )
            return 1
        try:
            summary = _write_ds9_human_decision_integrity_family()
        except (OSError, ValueError, RuntimeError) as exc:
            sys.stderr.write(f"DS9 C07 transition rejected: {exc}\n")
            return 1
        sys.stdout.write("materialized DS9 C07 register/report/status family\n")
        sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return 0

    if args.write_ds8b_post_freeze_transition:
        selected = {
            name
            for name, value in vars(args).items()
            if value is not None and value is not False
        }
        if selected != {
            "write_ds8b_post_freeze_transition",
            "write_report",
        }:
            sys.stderr.write(
                "DS8-B post-freeze transition requires only --write-report\n"
            )
            return 1
        try:
            transition = _write_ds8b_transition_family()
        except (OSError, ValueError, RuntimeError) as exc:
            sys.stderr.write(f"DS8-B transition rejected: {exc}\n")
            return 1
        sys.stdout.write("materialized DS8-B post-freeze register family\n")
        sys.stdout.write(
            json.dumps(
                {
                    "assignments": len(transition["assignments"]),
                    "changed_existing_paths": transition[
                        "changed_existing_path_count"
                    ],
                    "new_paths": transition["new_path_count"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return 0

    if args.write_c13_adjacent_print_export_resolution:
        selected = {
            name
            for name, value in vars(args).items()
            if value is not None and value is not False
        }
        if selected != {
            "write_c13_adjacent_print_export_resolution",
            "write_report",
        }:
            sys.stderr.write(
                "C13 print transition requires only --write-report\n"
            )
            return 1
        try:
            receipt = _write_c13_print_family()
        except (OSError, ValueError, RuntimeError) as exc:
            sys.stderr.write(f"C13 print transition rejected: {exc}\n")
            return 1
        sys.stdout.write("closed the independently verified C13 print predecessor\n")
        sys.stdout.write(
            json.dumps(
                {
                    "capture_count": len(receipt["captures"]),
                    "receipt_id": receipt["receipt_id"],
                    "snapshot_sha256": receipt["snapshot"]["sha256"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return 0

    if args.write_ds8_strangle_coverage:
        incompatible = any(
            (
                args.check,
                args.write_seed,
                args.write_supplemental,
                args.write_c03_vitest_resolution,
                args.write_c06_rendered_contrast_resolution,
                args.write_c11b_query_memory_root,
                args.write_c13_adjacent_print_export_resolution,
                args.migrate_c21b,
                args.migrate_c21c,
                args.print_c21b_authority_partition_hashes,
                args.print_c21b_authority_identity_literals,
                args.print_c21b_descriptor_identities,
                args.corruption_probes,
                args.verify_baseline_source_bytes,
                args.lint_results is not None,
                args.vitest_results is not None,
                args.architecture_results is not None,
            )
        )
        if incompatible or not args.write_report:
            sys.stderr.write(
                "DS8 strangle transition requires only --write-report\n"
            )
            return 1
        try:
            coverage = _write_ds8_strangle_family()
        except (OSError, ValueError, RuntimeError) as exc:
            sys.stderr.write(f"DS8 strangle transition rejected: {exc}\n")
            return 1
        sys.stdout.write("materialized DS8 strangle/register/status family\n")
        sys.stdout.write(
            json.dumps(
                {
                    "assignments": len(coverage["assignments"]),
                    "opening_production": coverage[
                        "opening_production_partition"
                    ],
                    "new_paths": coverage["new_path_count"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return 0

    if args.write_c06_rendered_contrast_resolution:
        incompatible = any(
            (
                args.check,
                args.write_seed,
                args.write_supplemental,
                args.write_c03_vitest_resolution,
                args.write_c11b_query_memory_root,
                args.write_c13_adjacent_print_export_resolution,
                args.write_ds8_strangle_coverage,
                args.migrate_c21b,
                args.migrate_c21c,
                args.print_c21b_authority_partition_hashes,
                args.print_c21b_authority_identity_literals,
                args.print_c21b_descriptor_identities,
                args.corruption_probes,
                args.verify_baseline_source_bytes,
                args.lint_results is not None,
                args.vitest_results is not None,
                args.architecture_results is not None,
            )
        )
        if incompatible or not args.write_report:
            sys.stderr.write(
                "C06 rendered-contrast transition requires only --write-report\n"
            )
            return 1

    if args.print_c21b_authority_partition_hashes:
        scan = _authority_presentation_scan()
        for error in [
            *_badge_classification_errors(scan),
            *_authority_prop_classification_errors(scan),
        ]:
            if "partition_hash_drift:" in error:
                print(error)
        return 0
    if args.print_c21b_authority_identity_literals:
        print(json.dumps({
            "badge": AUTHORITY_BADGE_CLASSIFICATIONS,
            "prop": AUTHORITY_PROP_IDENTITY_CLASSIFICATIONS,
        }, indent=2, sort_keys=True))
        return 0
    if args.print_c21b_descriptor_identities:
        print(json.dumps(_c21b_descriptor_identity_literals(), indent=2, sort_keys=True))
        return 0

    baseline_text = BASELINE_PATH.read_text(encoding="utf-8")
    if args.write_c03_vitest_resolution:
        try:
            baseline_text = _c03_resolved_baseline_manifest_text(baseline_text)
        except ValueError as exc:
            sys.stderr.write(f"C03 baseline transition rejected: {exc}\n")
            return 1
    if args.write_c03_vitest_resolution or args.write_supplemental:
        baseline_errors = validate_baseline_manifest(json.loads(baseline_text))
        if baseline_errors:
            for error in baseline_errors:
                sys.stderr.write(f"C03 baseline transition rejected: {error}\n")
            return 1
    if args.write_c03_vitest_resolution:
        BASELINE_PATH.write_text(baseline_text, encoding="utf-8")
        sys.stdout.write("transitioned the exact C03 Vitest receipt to C16 resolved\n")

    if args.write_seed:
        seed = build_seed_register()
        REGISTER_PATH.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {REGISTER_PATH.relative_to(REPO_ROOT)}")

    if not REGISTER_PATH.exists():
        print(f"missing register: {REGISTER_PATH}", file=sys.stderr)
        return 1
    register_text = REGISTER_PATH.read_text(encoding="utf-8")
    if args.write_c06_rendered_contrast_resolution:
        try:
            candidate_text = _c06_rendered_contrast_transition_text(register_text)
            candidate_data = json.loads(candidate_text)
            candidate_errors = validate_register(
                candidate_data,
                report_parity=False,
            )
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            sys.stderr.write(f"C06 rendered contrast transition rejected: {exc}\n")
            return 1
        if candidate_errors:
            for error in candidate_errors:
                sys.stderr.write(
                    f"C06 rendered contrast transition rejected: {error}\n"
                )
            return 1
        candidate_report = render_report(candidate_data)
        REGISTER_PATH.write_text(candidate_text, encoding="utf-8")
        REPORT_PATH.write_text(candidate_report, encoding="utf-8")
        sys.stdout.write("transitioned the exact C04 rendered-contrast row from C16\n")
        sys.stdout.write(f"wrote {REPORT_PATH.relative_to(REPO_ROOT)}\n")
        sys.stdout.write(
            json.dumps(_summary(candidate_data), indent=2, sort_keys=True) + "\n"
        )
        return 0
    if args.write_c11b_query_memory_root:
        register_text = _c11b_query_memory_transition_text(register_text)
        REGISTER_PATH.write_text(register_text, encoding="utf-8")
        print("transitioned cache-query-memory through the C11b owner writer")
    if args.write_supplemental:
        register_text = _refresh_supplemental_findings_text(register_text)
        REGISTER_PATH.write_text(register_text, encoding="utf-8")
        print(
            "refreshed "
            + str(REGISTER_PATH.relative_to(REPO_ROOT))
            + " supplemental_findings"
        )
    if args.migrate_c21b:
        register_text = _refresh_supplemental_findings_text(register_text)
        register_text = _c21b_surgical_identity_text(register_text)
        REGISTER_PATH.write_text(register_text, encoding="utf-8")
        print("migrated gated TypeScript references to C21a identities")
    if args.migrate_c21c:
        register_text = _c21c_surgical_identity_text(register_text)
        REGISTER_PATH.write_text(register_text, encoding="utf-8")
        print("migrated gated JSON/TOML references to C21c identities")
    data = json.loads(register_text)
    if args.write_report:
        REPORT_PATH.write_text(render_report(data), encoding="utf-8")
        print(f"wrote {REPORT_PATH.relative_to(REPO_ROOT)}")
    errors = validate_register(data)
    baseline = _load_json(BASELINE_PATH)
    if args.verify_baseline_source_bytes:
        errors.extend(
            "baseline_" + error
            for error in validate_baseline_manifest(
                baseline, verify_source_bytes=True
            )
        )
    if args.lint_results:
        errors.extend(compare_lint_results(baseline, args.lint_results))
    if args.vitest_results:
        errors.extend(compare_vitest_results(baseline, args.vitest_results))
    if args.architecture_results:
        errors.extend(compare_architecture_results(baseline, args.architecture_results))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.corruption_probes:
        failures = [
            *_corruption_probes(data),
            *_baseline_corruption_probes(baseline),
        ]
        if failures:
            print("corruption probes escaped: " + ", ".join(failures), file=sys.stderr)
            return 1
        print("corruption probes: PASS")
    print(json.dumps(_summary(data), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
