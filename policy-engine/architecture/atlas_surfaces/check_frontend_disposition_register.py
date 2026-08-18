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
import hashlib
import importlib.util
import io
import json
import posixpath
import re
import subprocess
import sys
import tomllib
import unittest
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

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

_TYPESCRIPT_REFERENCE_ROLES = frozenset(
    {
        "exported_declaration",
        "named_declaration",
        "variable_declaration",
        "type_property",
        "object_property",
        "call_expression",
        "string_literal",
        "import_binding",
        "jsx_opening",
        "jsx_attribute",
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
host.fileExists = (fileName) => virtualSource(fileName) !== undefined || defaultFileExists(fileName);
host.readFile = (fileName) => virtualSource(fileName) ?? defaultReadFile(fileName);
host.getSourceFile = (fileName, languageVersion, onError, shouldCreateNewSourceFile) => {
  const source = virtualSource(fileName);
  if (source !== undefined) {
    const kind = fileName.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
    return ts.createSourceFile(fileName, source, languageVersion, true, kind);
  }
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
  if ((ts.isPropertySignature(node) || ts.isPropertyAssignment(node)) && node.name) return qualifiedPropertyName(node);
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
    sources: Mapping[str, str], requests: Sequence[Mapping[str, str]]
) -> list[dict[str, Any]]:
    """Resolve many direct-syntax constructs through one TypeScript program."""
    for request in requests:
        role = request.get("role")
        if role not in _TYPESCRIPT_REFERENCE_ROLES:
            raise ValueError(f"typescript_reference_role_invalid:{role}")
    cache_key = hashlib.sha256(
        json.dumps(
            {
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


def _typescript_reference_identity_record(encoded_identity: str) -> dict[str, str]:
    """Decode one internally minted identity into the relocation-key input shape."""
    source_path, marker, encoded_payload = encoded_identity.partition("#ts-identity=")
    if not source_path or not marker:
        raise ValueError("typescript_reference_identity_invalid")
    payload = json.loads(
        base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
    )
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
        path_prefix, fragment, encoded_payload = encoded_identity.partition("#ts-identity=")
        if not fragment or not path_prefix or "#" in encoded_payload:
            raise ValueError
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        )
        version = payload["version"]
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
    if (
        version != 1
        or not isinstance(source_path, str)
        or not isinstance(role, str)
        or not isinstance(discriminator, str)
        or not isinstance(expected_chain, list)
        or not isinstance(expected_structural_path, list)
        or not isinstance(expected_tokens_sha256, str)
        or path_prefix != source_path
        or role not in _TYPESCRIPT_REFERENCE_ROLES
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
        "d333a5ad21d1303613a7a8a9ca08280afec38ed3437b56511e20c55bd66ab613",
    ),
    "architecture/atlas_surfaces/ds4-waist-debt-register.json:37": (
        "json",
        "/entries[debt_id=ds4-waist-decision-grade]",
        "37ae8c9313821507b034e2d085f342b8b2027236d78fcc9258ca50ee4ef69cfe",
    ),
    "architecture/atlas_surfaces/ds4-waist-debt-register.json:57": (
        "json",
        "/entries[debt_id=ds4-waist-cache-age]",
        "a5c57117f529287416ffd2acd55848298955a6c2f13c3ef43f332f2ed1927c4b",
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
                "apps/runtime-dashboard/src/api/types.ts#ts-identity=eyJkZW"
                "NsYXJhdGlvbl9jaGFpbiI6WyJ0eXBlX3Byb3BlcnR5OmNvbXBvbmVudHMu"
                "cGVybWlzc2lvbnMiLCJzeW1ib2w6cGVybWlzc2lvbnMiLCJyZXNvbHZlZD"
                "pwZXJtaXNzaW9ucyIsImRlY2xhcmF0aW9uOmFwcHMvcnVudGltZS1kYXNo"
                "Ym9hcmQvc3JjL2FwaS90eXBlcy50czpQcm9wZXJ0eVNpZ25hdHVyZSJdLC"
                "JkaXNjcmltaW5hdG9yIjoiY29tcG9uZW50cy5wZXJtaXNzaW9ucyIsIm5v"
                "cm1hbGl6ZWRfdG9rZW5zX3NoYTI1NiI6IjBjYWQ3NjY3ZjcyN2Q3MjE1ND"
                "k2YmZmNGM0MGExNDc2NmZkZWZkZjA5ZWIxOTQzODhjMzU4ZDU1MzEzYTY3"
                "OGMiLCJyb2xlIjoidHlwZV9wcm9wZXJ0eSIsInNvdXJjZV9wYXRoIjoiYX"
                "Bwcy9ydW50aW1lLWRhc2hib2FyZC9zcmMvYXBpL3R5cGVzLnRzIiwic3Ry"
                "dWN0dXJhbF9wYXRoIjpbIlByb3BlcnR5U2lnbmF0dXJlOjIiLCJUeXBlTG"
                "l0ZXJhbDoxIiwiUHJvcGVydHlTaWduYXR1cmU6MzciLCJUeXBlTGl0ZXJh"
                "bDoxIiwiUHJvcGVydHlTaWduYXR1cmU6NSJdLCJ2ZXJzaW9uIjoxfQ"
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
            (
                "apps/runtime-dashboard/src/api/queryKeys.ts#ts-identity=eyJkZWNsYXJh"
                "dGlvbl9jaGFpbiI6WyJ2YXJpYWJsZTpxdWVyeUtleXMiLCJzeW1ib2w6cXVlcnlLZXlz"
                "IiwicmVzb2x2ZWQ6cXVlcnlLZXlzIiwiZGVjbGFyYXRpb246YXBwcy9ydW50aW1lLWRh"
                "c2hib2FyZC9zcmMvYXBpL3F1ZXJ5S2V5cy50czpWYXJpYWJsZURlY2xhcmF0aW9uIl0s"
                "ImRpc2NyaW1pbmF0b3IiOiJxdWVyeUtleXMiLCJub3JtYWxpemVkX3Rva2Vuc19zaGEy"
                "NTYiOiI3NmU4ZDRlOGQ1NzdkZGNhNGI2MDgzOTY2OWZlM2VjNmM0NGEwOGVmZTk0OWYw"
                "YTllODVjZjhjZTFiNjA3NGQ5Iiwicm9sZSI6InZhcmlhYmxlX2RlY2xhcmF0aW9uIiwi"
                "c291cmNlX3BhdGgiOiJhcHBzL3J1bnRpbWUtZGFzaGJvYXJkL3NyYy9hcGkvcXVlcnlL"
                "ZXlzLnRzIiwic3RydWN0dXJhbF9wYXRoIjpbIkZpcnN0U3RhdGVtZW50OjMiLCJWYXJp"
                "YWJsZURlY2xhcmF0aW9uTGlzdDoxIiwiVmFyaWFibGVEZWNsYXJhdGlvbjowIl0sInZl"
                "cnNpb24iOjF9"
            ),
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
    "c06-queryobserver-cache-posture-artifact-debt": {
        "finding_kind": "producer_binding_debt",
        "disposition": "rebind_pending",
        "status": "open_debt",
        "owner_slice": "DS5",
        "capability_states": [
            "artifact_missing",
            "bridge_missing",
            "consumer_missing",
            "verification_missing",
            "surface_missing",
            "semantic_test_missing",
        ],
        "evidence_refs": [
            "src/polisyos/runtime/http/services/governed_projections.py:121",
            (
                "apps/runtime-dashboard/src/features/runs/api/useDepthNCycl"
                "eBoardProjection.ts#ts-identity=eyJkZWNsYXJhdGlvbl9jaGFpbi"
                "I6WyJleHBvcnQ6ZGVwdGhOQ3ljbGVCb2FyZFByb2plY3Rpb25RdWVyeU9w"
                "dGlvbnMiLCJzeW1ib2w6ZGVwdGhOQ3ljbGVCb2FyZFByb2plY3Rpb25RdW"
                "VyeU9wdGlvbnMiLCJyZXNvbHZlZDpkZXB0aE5DeWNsZUJvYXJkUHJvamVj"
                "dGlvblF1ZXJ5T3B0aW9ucyIsImRlY2xhcmF0aW9uOmFwcHMvcnVudGltZS"
                "1kYXNoYm9hcmQvc3JjL2ZlYXR1cmVzL3J1bnMvYXBpL3VzZURlcHRoTkN5"
                "Y2xlQm9hcmRQcm9qZWN0aW9uLnRzOkZ1bmN0aW9uRGVjbGFyYXRpb24iXS"
                "wiZGlzY3JpbWluYXRvciI6ImRlcHRoTkN5Y2xlQm9hcmRQcm9qZWN0aW9u"
                "UXVlcnlPcHRpb25zIiwibm9ybWFsaXplZF90b2tlbnNfc2hhMjU2IjoiZT"
                "ZkYWZmZjEwY2VhMGYwNDkzMTNhZmM5ZGMxMTNlNjQ2YzQwYTdkNzU1MmJj"
                "Yzc4NmFkZGRlZGNhOTk4NWI4YiIsInJvbGUiOiJleHBvcnRlZF9kZWNsYX"
                "JhdGlvbiIsInNvdXJjZV9wYXRoIjoiYXBwcy9ydW50aW1lLWRhc2hib2Fy"
                "ZC9zcmMvZmVhdHVyZXMvcnVucy9hcGkvdXNlRGVwdGhOQ3ljbGVCb2FyZF"
                "Byb2plY3Rpb24udHMiLCJzdHJ1Y3R1cmFsX3BhdGgiOltdLCJ2ZXJzaW9u"
                "IjoxfQ"
            ),
            _C21C_FROZEN_STRUCTURED_IDENTITIES[
                "architecture/atlas_surfaces/ds4-waist-debt-register.json:57"
            ],
            "docs/plans/active/atlas-slices/DS5-enforcement-waist.md#ds5-c11a",
        ],
        "rationale": (
            "QueryObserver emits lifecycle signals today, but no typed CachePosture "
            "artifact exists. ProjectionFreshness records source observation and is "
            "orthogonal to cached-copy posture; C11a/C11b own the client artifact, "
            "bridge, and surface."
        ),
        "closure_signal": (
            "python3 -m unittest architecture.atlas_surfaces.test_atlas_enforcement."
            "AtlasEnforcementTests.test_queryobserver_cache_posture_keeps_source_"
            "freshness_orthogonal exits 0 after C11a/C11b publish the typed "
            "QueryObserver cache-posture artifact without reclassifying source freshness"
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
        "owner_slice": "DS3",
        "capability_states": ["producer_missing", "surface_missing"],
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
                "packages/runtime-api-client/types.ts#ts-identity=eyJkZWNsY"
                "XJhdGlvbl9jaGFpbiI6WyJ0eXBlX3Byb3BlcnR5OmNvbXBvbmVudHMuUnV"
                "uU3VtbWFyeSIsInN5bWJvbDpSdW5TdW1tYXJ5IiwicmVzb2x2ZWQ6UnVuU"
                "3VtbWFyeSIsImRlY2xhcmF0aW9uOnBhY2thZ2VzL3J1bnRpbWUtYXBpLWN"
                "saWVudC90eXBlcy50czpQcm9wZXJ0eVNpZ25hdHVyZSJdLCJkaXNjcmlta"
                "W5hdG9yIjoiY29tcG9uZW50cy5SdW5TdW1tYXJ5Iiwibm9ybWFsaXplZF9"
                "0b2tlbnNfc2hhMjU2IjoiNzE0Zjk1ZTEyMWFmYzU1OGI5MjQ3NDFjMDk0O"
                "DIyZjExMDA1NTEwY2Y4MjM4ZWI1ODBjZGIzNmFjZmMzYWZmYyIsInJvbGU"
                "iOiJ0eXBlX3Byb3BlcnR5Iiwic291cmNlX3BhdGgiOiJwYWNrYWdlcy9yd"
                "W50aW1lLWFwaS1jbGllbnQvdHlwZXMudHMiLCJzdHJ1Y3R1cmFsX3BhdGg"
                "iOlsiUHJvcGVydHlTaWduYXR1cmU6MiIsIlR5cGVMaXRlcmFsOjEiLCJQc"
                "m9wZXJ0eVNpZ25hdHVyZToyOTQiXSwidmVyc2lvbiI6MX0"
            ),
            (
                "packages/runtime-api-client/types.ts#ts-identity=eyJkZWNsY"
                "XJhdGlvbl9jaGFpbiI6WyJ0eXBlX3Byb3BlcnR5OmNvbXBvbmVudHMuZml"
                "uaXNoZWRfYXQiLCJzeW1ib2w6ZmluaXNoZWRfYXQiLCJyZXNvbHZlZDpma"
                "W5pc2hlZF9hdCIsImRlY2xhcmF0aW9uOnBhY2thZ2VzL3J1bnRpbWUtYXB"
                "pLWNsaWVudC90eXBlcy50czpQcm9wZXJ0eVNpZ25hdHVyZSJdLCJkaXNjc"
                "mltaW5hdG9yIjoiY29tcG9uZW50cy5maW5pc2hlZF9hdCIsIm5vcm1hbGl"
                "6ZWRfdG9rZW5zX3NoYTI1NiI6IjQxOTY2ZjRkZTYwODFiNmQ2OGFmZmZjY"
                "jJiZWRlNTQ2OGY5NjljNzg5NzI3ZWVkNjg3ZTc4MGNlNzE2MDY4YjIiLCJ"
                "yb2xlIjoidHlwZV9wcm9wZXJ0eSIsInNvdXJjZV9wYXRoIjoicGFja2FnZ"
                "XMvcnVudGltZS1hcGktY2xpZW50L3R5cGVzLnRzIiwic3RydWN0dXJhbF9"
                "wYXRoIjpbIlByb3BlcnR5U2lnbmF0dXJlOjIiLCJUeXBlTGl0ZXJhbDoxI"
                "iwiUHJvcGVydHlTaWduYXR1cmU6Mjk0IiwiVHlwZUxpdGVyYWw6MSIsIlB"
                "yb3BlcnR5U2lnbmF0dXJlOjgiXSwidmVyc2lvbiI6MX0"
            ),
            (
                "packages/runtime-api-client/types.ts#ts-identity=eyJkZWNsY"
                "XJhdGlvbl9jaGFpbiI6WyJ0eXBlX3Byb3BlcnR5OmNvbXBvbmVudHMuc3R"
                "hdHVzIiwic3ltYm9sOnN0YXR1cyIsInJlc29sdmVkOnN0YXR1cyIsImRlY"
                "2xhcmF0aW9uOnBhY2thZ2VzL3J1bnRpbWUtYXBpLWNsaWVudC90eXBlcy5"
                "0czpQcm9wZXJ0eVNpZ25hdHVyZSJdLCJkaXNjcmltaW5hdG9yIjoiY29tc"
                "G9uZW50cy5zdGF0dXMiLCJub3JtYWxpemVkX3Rva2Vuc19zaGEyNTYiOiI"
                "xN2U2NzM1NGM0ZWI2OWU5MzA1MGM0ZWI3MzJjZWU0ZDU0MWU5OWU2OTJiN"
                "TE1NGE5NDBhNTI2NGViODllODlmIiwicm9sZSI6InR5cGVfcHJvcGVydHk"
                "iLCJzb3VyY2VfcGF0aCI6InBhY2thZ2VzL3J1bnRpbWUtYXBpLWNsaWVud"
                "C90eXBlcy50cyIsInN0cnVjdHVyYWxfcGF0aCI6WyJQcm9wZXJ0eVNpZ25"
                "hdHVyZToyIiwiVHlwZUxpdGVyYWw6MSIsIlByb3BlcnR5U2lnbmF0dXJlO"
                "jI5NCIsIlR5cGVMaXRlcmFsOjEiLCJQcm9wZXJ0eVNpZ25hdHVyZToxNSJ"
                "dLCJ2ZXJzaW9uIjoxfQ"
            ),
            "src/polisyos/runtime/http/routes/runs.py:179",
            "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:602",
        ],
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
            "apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx",
            "apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx",
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
    "prop-time-semantics-freshness": {
        "classification": "debt",
        "component": "TimeSemanticsLabel",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/temporal/TimeSemanticsLabel.tsx",
        "prop": "freshness",
        "consumer_paths": [
            "apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx",
            "apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx",
        ],
        "owner_slice": "DS18",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "the generated owner freshness value enters an issued temporal presentation with explicit unknown behavior"
        ),
    },
    "prop-dispute-status": {
        "classification": "debt",
        "component": "DisputeBadge",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/trust-view/DisputeBadge.tsx",
        "prop": "status",
        "consumer_paths": [
            "apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.tsx",
            "apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx",
        ],
        "owner_slice": "DS11",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a private exhaustive dispute issuer owns clothing and runtime-novel dispute states render unrecognized"
        ),
    },
    "prop-verification-status-icon-tone": {
        "classification": "debt",
        "component": "StatusIcon",
        "component_declaration_path": "apps/runtime-dashboard/src/shared/ui/trust-view/VerificationStatus.tsx",
        "prop": "tone",
        "consumer_paths": [
            "apps/runtime-dashboard/src/shared/ui/trust-view/VerificationStatus.tsx"
        ],
        "owner_slice": "DS11",
        "capability_states": ["verification_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "the open string tone carrier is replaced by a private issued trust presentation and structural forgery is rejected"
        ),
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
            "apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx",
        ],
    },
    "prop-envelope-authority-purpose": {
        "classification": "branded:governed_authority_purpose",
        "component": "EnvelopeChip",
        "component_declaration_path": "packages/atlas-ui/src/primitives/EnvelopeChip.tsx",
        "prop": "authorityPurpose",
        "consumer_paths": [
            "apps/runtime-dashboard/src/shared/ui/compounds/DecisionCard.tsx",
            "apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx",
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
        "capability_states": ["consumer_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a generated review-required fact enters a private issuer and missing or denied inputs cannot present positive"
        ),
    },
    "badge-bureaucratic-legal-review": {
        "owner_slice": "DS9",
        "capability_states": ["consumer_missing", "verification_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a generated legal-review union enters an exhaustive issuer and runtime novelty renders unrecognized"
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
        "capability_states": ["producer_missing", "bridge_missing", "consumer_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "generated approval, calibration, and gate DTOs use weakest-boundary mixed-outcome tests"
        ),
    },
    "badge-promotion-candidate-status": {
        "owner_slice": "DS15",
        "capability_states": ["consumer_missing", "verification_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a generated promotion union enters a private issuer and novel values render unrecognized"
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
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a generated owner severity field enters a branded issuer with runtime novelty"
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
    "badge-governed-projection-rights-bar": {
        "owner_slice": "DS5",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a generated may_not_use_for item enters a branded veto presentation"
        ),
    },
    "badge-governed-source-validation": {
        "owner_slice": "DS7",
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "generated source validation status enters an exhaustive issuer with novelty tests"
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
        "capability_states": ["bridge_missing", "semantic_test_missing"],
        "closure_signal": _authority_closure(
            "a typed governance summary proves counts cannot synthesize composed authority"
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

BENIGN_BADGE_BASES = (
    "interaction_or_editor_state",
    "transport_or_runtime_health",
    "workflow_or_lifecycle_display_without_terminality_inference",
    "layout_or_counts",
    "opaque_metadata_or_taxonomy",
)

BENIGN_BADGE_CLASS_COUNTS: dict[str, int] = {
    "interaction_or_editor_state": 13,
    "transport_or_runtime_health": 20,
    "workflow_or_lifecycle_display_without_terminality_inference": 24,
    "layout_or_counts": 21,
    "opaque_metadata_or_taxonomy": 25,
}

if set(BENIGN_BADGE_CLASS_COUNTS) != set(BENIGN_BADGE_BASES):
    raise RuntimeError("benign Badge class vocabulary drift")
if sum(BENIGN_BADGE_CLASS_COUNTS.values()) != 103:
    raise RuntimeError("benign Badge class count drift")

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
    "badge_total": 163,
    "badge_branded": 2,
    "badge_debt": 58,
    "badge_benign": 103,
    "prop_total": 19,
    "prop_branded": 2,
    "prop_debt": 12,
    "prop_benign": 5,
    "prop_use_total": 35,
    "prop_use_branded": 6,
    "prop_use_debt": 21,
    "prop_use_benign": 8,
}
AUTHORITY_BADGE_PARTITION_SHA256 = (
    "sha256:aa5d8636a6ddd55d5769c91044d5507611af9c9e013fc18078e2a48926f9f0ff"
)
AUTHORITY_PROP_PARTITION_SHA256 = (
    "sha256:c8873b4644cee24a3bb33fdd539644c2dadfdbf56b5e4d5617ed40d78409cfe1"
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


@lru_cache(maxsize=1)
def _authority_presentation_scan() -> dict[str, Any]:
    """Return the live finite sink census; no value-flow inference is performed."""
    return status_checker._scan(
        authority_prop_descriptors=_authority_prop_descriptors()
    )


def _site_location(site: Mapping[str, Any]) -> tuple[str, int]:
    return (str(site.get("path", "")), int(site.get("line", 0)))


def _badge_classification_errors(
    scan: Mapping[str, Any],
    classifications: Mapping[str, str] | None = None,
) -> list[str]:
    """Validate the exact 163-site Badge partition as a finite set property."""
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
    """Validate the exact declaration/use identity of all 19 prop groups."""
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
        if spec["classification"] != "debt":
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
    '0963299bc8c2f44481a04d9a53aa44b6d0cd19eb5b738dcfae62517cadc7f1db': (
        'debt:badge-governed-source-validation'
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
    '1e5efb80b85a26f8549c7d5a8ca3052496ff1ed8767b8cb8d12485b4704aeb7b': (
        'debt:badge-governed-projection-availability'
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
    '5a3bada810ad2a1c0b65fe6b458bfeadf3e8a641046b873a86c26b8d89cad2ef': (
        'benign:opaque_metadata_or_taxonomy'
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
    '8cb41cd36e24b70818f36d6f19392fd3c04f326382d61cbc631e03ff15a544dc': (
        'debt:badge-governed-projection-availability'
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
    '98ca189a06de16043ec40ca09c3d74f2b63a524ff10299c3561539dbea882f56': (
        'debt:badge-governed-projection-rights-bar'
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
    '161ada920d42be7ec2d8a0dfd475ae9abd0de9bb4c611601f93afbf43bd5616b': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-time-semantics-freshness',
            'role': 'prop_declaration',
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
    '29d0fb4a9758c4cacc733fa47028dd641f098c1df02b1711b214edbc52912d05': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-data-freshness',
            'role': 'consumer',
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
    '73ac833708a0af8050ac16602ceb7cea2c0fc956868ac75bb17143960f24eec4': [
        {
            'classification': 'branded:governed_authority_purpose',
            'descriptor_id': 'prop-envelope-authority-purpose',
            'role': 'consumer',
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
    '9156023f5437ed35cbd33f0b0cf42bcd52ba029088f23fd0b05e0e24d5d445ef': [
        {
            'classification': 'branded:authority_presentation',
            'descriptor_id': 'prop-authority-badge-presentation',
            'role': 'consumer',
        },
    ],
    '94527927d03d160ca987ac01d71d4894b66f35ade816cbf1324a114e7084b373': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-time-semantics-freshness',
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
    'a0f28b1b52ff75f30a27d6f75cfe34c2fc1d9ab9a4c0d0230d431aa73aa6fbe4': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-data-freshness',
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
    'bbba02809125cc44d061c07208227cfd0a110963de7e507daeb434db0efa9644': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-time-semantics-freshness',
            'role': 'consumer',
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
    'f1663c94e21b16352db7368cd12538ef545d06fbb71e6b717d9624cd8e36f163': [
        {
            'classification': 'debt',
            'descriptor_id': 'prop-time-semantics-freshness',
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
    """Build the 39 typed debt rows from the live finite census."""
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
        finding_id = "authority-presentation-" + group_id
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
                "decision_date": DS5_C01A_DECISION_DATE,
                "rationale": (
                    "C01a classifies this direct authority-bearing Badge group "
                    "as unbranded typed debt; its owner must replace caller-chosen "
                    "clothing with the existing private-issuer brand pattern."
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
            if finding_id not in expected_by_id:
                errors.append(
                    "authority_presentation_debt_descriptor_missing:" + finding_id
                )
    if live_probes:
        errors.extend(_badge_classification_errors(authority_scan))
        errors.extend(_authority_prop_classification_errors(authority_scan))
    return errors

GOVERNED_DEBT_DESCRIPTORS = {
    finding_id: {
        "finding_id": finding_id,
        **copy.deepcopy(descriptor),
        "decision_date": descriptor.get("decision_date", DECISION_DATE),
    }
    for finding_id, descriptor in PRODUCER_BINDING_DEBT_DESCRIPTORS.items()
}
GOVERNED_DEBT_DESCRIPTORS.update(copy.deepcopy(INTEGRATE_DEBT_DESCRIPTORS))

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
    "apps/runtime-dashboard/src/features/runs/components/readinessScientificContainment.test.ts",
]
C23_RATIONALE = (
    "C23 deleted dashboard-local readiness and scientific synthesis; the retained panels "
    "emit unavailable until DS16 provides producer-signed fields or registered typed refusal."
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
)

REPORT_PROJECTION_START = "<!-- BEGIN DS19 REGISTER PROJECTION -->"
REPORT_PROJECTION_END = "<!-- END DS19 REGISTER PROJECTION -->"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


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


def _typescript_identity_reference_errors(references: Sequence[str]) -> list[str]:
    """Batch-validate every stored C21a identity against one source snapshot."""
    parsed: list[tuple[str, dict[str, Any]]] = []
    for reference in references:
        if "#ts-identity=" not in reference:
            continue
        try:
            path, payload_text = reference.split("#ts-identity=", 1)
            payload = json.loads(
                base64.urlsafe_b64decode(payload_text + "=" * (-len(payload_text) % 4))
            )
            if (
                payload["version"] != 1
                or payload["source_path"] != path
                or payload["role"] not in _TYPESCRIPT_REFERENCE_ROLES
            ):
                raise ValueError
        except (KeyError, ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError):
            return ["typescript_reference_identity_invalid"]
        parsed.append((reference, payload))
    if not parsed:
        return []
    sources = {
        str(payload["source_path"]): (REPO_ROOT / str(payload["source_path"])).read_text(encoding="utf-8")
        for _reference, payload in parsed
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
        _typescript_reference_construct_facts_batch(sources, requests),
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
    "packages/runtime-api-client/canonicalRuntimeApiClient.ts:865": ("exported_declaration", "RunSummary"),
    "packages/runtime-api-client/types.ts:9240": ("type_property", "components.RunSummary"),
    "packages/runtime-api-client/types.ts:9258": ("type_property", "components.finished_at"),
    "packages/runtime-api-client/types.ts:9284": ("type_property", "components.status"),
    "apps/runtime-dashboard/src/features/runs/api/useDepthNCycleBoardProjection.ts:103": ("exported_declaration", "depthNCycleBoardProjectionQueryOptions"),
    "packages/runtime-api-client/types.ts:2411": ("type_property", "components.AuthMeResponse"),
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
    "packages/runtime-api-client/types.ts:2430": ("type_property", "components.permissions"),
    "apps/runtime-dashboard/src/api/types.ts:2323": ("type_property", "components.permissions"),
}


def _c21c_structured_identity_literals() -> dict[str, str]:
    """Return the six C21c identities; line hints are migration-only."""
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
    elif re.search(r"\bexport\s+(?:async\s+)?function\s+(?:build|verify)SignedPublicDecisionPacket\b", source_line):
        role, discriminator = "exported_declaration", re.search(r"(?:build|verify)SignedPublicDecisionPacket", source_line).group(0)
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
    if len(structured) != 6 or set(structured) != set(
        _C21C_FROZEN_STRUCTURED_IDENTITIES.values()
    ):
        raise ValueError("c21c_structured_identity_partition_drift")
    if any(reference in references for reference in _C21C_STRUCTURED_HINTS):
        raise ValueError("c21c_legacy_structured_line_reference")
    line_reference_re = re.compile(r"^(.*?):\d+(?::\d+)?$")
    line_references = [
        reference for reference in references if line_reference_re.match(reference)
    ]
    if len(line_references) != 15 or len(
        {
            line_reference_re.match(reference).group(1)
            for reference in line_references
        }
    ) != 11:
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


def _supplemental_findings() -> list[dict[str, Any]]:
    baseline_ref = "architecture/atlas_surfaces/frontend-baseline-debt-manifest.json"
    baseline = _load_json(BASELINE_PATH)
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
            "The active manifest retains exactly three count-sensitive locale parity identities owned by DS6.",
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
        is_open = (
            baseline["lint"]["error_count"] > 0
            if finding_id == "baseline-lint-quantity-debt"
            else active_class is not None
        )
        findings.append({
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
        })
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
    return findings


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
    """Return descriptor rows and unsupported producer rows owned by refresh."""
    descriptor_ids = set(GOVERNED_DEBT_DESCRIPTORS) | set(
        AUTHORITY_PRESENTATION_DEBT_SPECS
    )
    _start, _end, spans = _supplemental_section_spans(text)
    for finding_id, object_start, object_end in spans:
        row = json.loads(text[object_start : object_end + 1])
        if (
            row.get("finding_kind") == "producer_binding_debt"
            and finding_id not in descriptor_ids
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


def _refresh_supplemental_findings_text(text: str) -> str:
    """Upsert descriptor rows while preserving every other register byte."""
    descriptor_ids = set(GOVERNED_DEBT_DESCRIPTORS) | set(AUTHORITY_PRESENTATION_DEBT_SPECS)
    generated = {
        row["finding_id"]: row
        for row in _supplemental_findings()
        if row["finding_id"] in descriptor_ids
    }
    refresh_owned_ids = _surgical_supplemental_finding_ids(text)
    refreshed = text
    for finding_id in sorted(refresh_owned_ids - descriptor_ids):
        refreshed = _remove_supplemental_finding_text(refreshed, finding_id)

    _start, _end, spans = _supplemental_section_spans(refreshed)
    seen: set[str] = set()
    for finding_id, object_start, object_end in reversed(spans):
        if finding_id not in generated:
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
        "schema_version": "1.0",
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

    failures = _flatten_vitest_failures(baseline)
    if len(failures) != baseline["vitest"]["tests"]["failed"] or len(failures) != 3:
        errors.append("vitest_baseline_failure_count_drift")
    surviving_vitest_classes = {
        (
            debt_class["class_id"],
            debt_class["owner_slice"],
            debt_class["failure_count"],
        )
        for debt_class in baseline["vitest"]["debt_classes"]
    }
    if surviving_vitest_classes != {
        ("i18n-count-message-parity", "DS6", 3)
    }:
        errors.append("vitest_surviving_debt_owner_drift")
    if _canonical_sha256(failures) != baseline["vitest"]["failure_set"]["sha256"]:
        errors.append("vitest_baseline_payload_hash_drift")
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
    raw = json.loads(raw_results_path.read_text(encoding="utf-8"))
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


def validate_register(
    data: Mapping[str, Any],
    *,
    live_probes: bool = True,
    schema: bool = True,
    report_parity: bool = True,
    direct_transport_sources: Mapping[str, str] | None = None,
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
            for row in _supplemental_findings()
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
        baseline = _load_json(BASELINE_PATH)
        errors.extend(
            "baseline_" + error for error in validate_baseline_manifest(baseline)
        )
        findings_by_id = {
            row["finding_id"]: row for row in data["supplemental_findings"]
        }
        active_test_classes = {
            row["class_id"]: row for row in baseline["vitest"]["debt_classes"]
        }
        expected_debt_lifecycle = {
            "baseline-lint-quantity-debt": (
                "open_debt" if baseline["lint"]["error_count"] > 0 else "repaired",
                "DS4",
            ),
            "baseline-test-i18n-count-debt": (
                "open_debt"
                if "i18n-count-message-parity" in active_test_classes
                else "repaired",
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

    for name, mutation in probes:
        if not validate_register(mutation, live_probes=False, report_parity=False):
            failures.append(name)

    authority_scan = _authority_presentation_scan()
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
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate the committed register")
    parser.add_argument("--write-seed", action="store_true", help="write a fresh deterministic seed register")
    parser.add_argument(
        "--write-supplemental",
        action="store_true",
        help="refresh only descriptor-derived supplemental findings in the evolved register",
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

    if args.write_seed:
        seed = build_seed_register()
        REGISTER_PATH.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {REGISTER_PATH.relative_to(REPO_ROOT)}")

    if not REGISTER_PATH.exists():
        print(f"missing register: {REGISTER_PATH}", file=sys.stderr)
        return 1
    register_text = REGISTER_PATH.read_text(encoding="utf-8")
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
