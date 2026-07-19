"""Validate and seed the Atlas DS19 frontend disposition register.

The register is a projection over the DS1 readiness ledger and DS2 adoption
ledger.  This checker recomputes those joins, validates the strict schema, and
executes live filesystem/reference probes for every terminal deletion or
rebound claim.  Stored counts and empty arrays are never accepted as proof.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import posixpath
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
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

_TS_MODULE_FACTS_SCRIPT = r"""
import ts from "typescript";

let raw = "";
for await (const chunk of process.stdin) raw += chunk;
const sources = JSON.parse(raw);
const facts = [];
const compilerOptions = {
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
      if (clause && !clause.isTypeOnly) {
        const names = [];
        const usedNames = [];
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
            }
          }
        } else if (bindings && ts.isNamespaceImport(bindings)) {
          namespace = bindings.name.text;
          namespaceUsed = bindingHasValueUse(bindings.name);
        }
        facts.push({
          path,
          kind: "static",
          module: node.moduleSpecifier.text,
          names,
          exported_names: [],
          used_names: usedNames,
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
}

EXPECTED_FINDING_IDS = {
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


def _recompute_probe(probe: Mapping[str, Any]) -> list[str]:
    if probe["kind"] == "path_absent":
        return sorted(target for target in probe["targets"] if (REPO_ROOT / target).exists())
    if probe["kind"] == "protected_live_consumers":
        return sorted(target for target in probe["targets"] if (REPO_ROOT / target).exists())
    if probe["kind"] == "typescript_symbol_consumer_census":
        sources = _typescript_production_sources(probe["scan_roots"])
        return _ui_primitive_consumers_from_sources(sources)
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
    open_findings = [
        (
            "baseline-lint-quantity-debt",
            "baseline_lint_debt",
            f"{baseline_ref}#lint",
            "The exact 75 policyos/quantity-must-be-wrapped diagnostics are DS4 quantity-family rebinding debt; DS19 admits no new diagnostic.",
        ),
        (
            "baseline-test-i18n-count-debt",
            "baseline_test_debt",
            f"{baseline_ref}#tests/i18n-count",
            "Three count-sensitive locale parity failures reproduce on the parent and belong to DS4 quantity/message rebinding.",
        ),
        (
            "baseline-test-a11y-coverage-debt",
            "baseline_test_debt",
            f"{baseline_ref}#tests/a11y-coverage",
            "The missing OperatorDiagnosticPanel a11y companion reproduces on the parent and belongs to the DS4 harness repair.",
        ),
        (
            "baseline-test-temporal-cursor-debt",
            "baseline_test_debt",
            f"{baseline_ref}#tests/temporal-cursor",
            "The time-dependent canonical URL assertion reproduces on the parent and belongs to DS4 temporal primitive verification.",
        ),
    ]
    findings: list[dict[str, Any]] = [
        {
            "finding_id": finding_id,
            "finding_kind": kind,
            "disposition": "rebind_pending",
            "status": "open_debt",
            "evidence_refs": [evidence_ref],
            "owner_slice": "DS4",
            "decision_date": DECISION_DATE,
            "rationale": rationale,
        }
        for finding_id, kind, evidence_ref, rationale in open_findings
    ]
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
    return findings


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
    """Build the deterministic DS19 seed from the two source ledgers."""
    ds1 = _load_json(DS1_PATH)
    ds2 = _load_json(DS2_PATH)
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
        "quantity_enveloped": 12,
        "authority_guess_removed": 5,
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
    for resolution in lint["resolutions"]:
        identity_id = resolution["origin_identity_sha256"]
        if (
            resolution["cluster_id"] == "C06"
            and resolution["semantic_kind"] == "decision_bearing"
            and resolution["closure_test_ref"]
            != "apps/runtime-dashboard/src/shared/ui/quantity/quantityDecisionProducers.test.tsx"
        ):
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
        or architecture["producer_sha256"]
        != architecture_origin["producer_sha256"]
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
    if len(failures) != baseline["vitest"]["tests"]["failed"] or len(failures) != 5:
        errors.append("vitest_baseline_failure_count_drift")
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
            if class_id == "temporal-cursor-canonical-url":
                if "valid_at=2026-04-15T12%3A00%3A00.000Z" not in messages:
                    errors.append(f"vitest_failure_signature_drift:{file_path}:{full_name}")
            elif anchor not in messages:
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
    unexpected_package = sorted(atlas_exports - UI_PRIMITIVES_PACKAGE_MIGRATED)
    if missing_package:
        errors.append(f"ui_primitives_package_exports_missing:{missing_package}")
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


def validate_register(
    data: Mapping[str, Any],
    *,
    live_probes: bool = True,
    schema: bool = True,
    report_parity: bool = True,
) -> list[str]:
    """Return all schema, parity, composition, and live-census failures."""
    errors: list[str] = []
    if schema:
        errors.extend(_schema_errors(data, SCHEMA_PATH))
        if errors:
            return errors
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
    for unit in [*entries, *data["subunits"]]:
        _validate_composition(unit, censuses, errors)

    if live_probes:
        for census in data["reference_censuses"]:
            for probe in census["probes"]:
                observed = _recompute_probe(probe)
                if observed != probe["observed_refs"]:
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
            if probe["kind"] == "reference_count"
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
    active_id, active_row = _lint_identity_rows(overlapping_lint["lint"])[0]
    overlapping_lint["lint"]["resolutions"][0]["origin_identity_sha256"] = active_id
    overlapping_lint["lint"]["resolutions"][0]["origin_identity"] = active_row
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
    probes.append(("lint-empty-active-incomplete-resolutions", empty_without_resolutions))

    missing_architecture = copy.deepcopy(baseline)
    missing_architecture["architecture"]["resolutions"].pop()
    probes.append(("architecture-missing-resolution", missing_architecture))

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

    failures = []
    for name, mutation in probes:
        if not validate_register(mutation, live_probes=False, report_parity=False):
            failures.append(name)
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

    lines.extend(
        [
            "",
            "### Subunits and structural findings",
            "",
            "| ID | Kind | Disposition | Owner slice | State/reason |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in data["subunits"]:
        lines.append(
            f"| `{row['unit_id']}` | `{row['scope_kind']}` | `{row['disposition']}` | `{row['owner_slice']}` | {row['rationale']} |"
        )
    for row in data["supplemental_findings"]:
        lines.append(
            f"| `{row['finding_id']}` | `{row['finding_kind']}` | `{row['disposition']}` | `{row['owner_slice']}` | `{row['status']}` — {row['rationale']} |"
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
| Register/check | schema, 261 DS1 roots, 233 DS2 edges, seven live censuses, report parity, links, source hashes, and corruption probes PASS | disposition authority current |
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
    return {
        "root_entries": len(data["entries"]),
        "root_dispositions": dict(sorted(Counter(entry["disposition"] for entry in data["entries"]).items())),
        "subunit_dispositions": dict(sorted(Counter(entry["disposition"] for entry in data["subunits"]).items())),
        "censuses": len(data["reference_censuses"]),
        "supplemental_findings": len(data["supplemental_findings"]),
        "seeded_negatives": len(data["seeded_negative_lifecycle"]),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate the committed register")
    parser.add_argument("--write-seed", action="store_true", help="write a fresh deterministic seed register")
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

    if args.write_seed:
        seed = build_seed_register()
        REGISTER_PATH.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {REGISTER_PATH.relative_to(REPO_ROOT)}")

    if not REGISTER_PATH.exists():
        print(f"missing register: {REGISTER_PATH}", file=sys.stderr)
        return 1
    data = _load_json(REGISTER_PATH)
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
