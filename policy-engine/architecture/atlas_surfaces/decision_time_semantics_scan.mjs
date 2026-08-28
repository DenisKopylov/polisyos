#!/usr/bin/env node

/** Enumerate every production dashboard TS/TSX file and its render/export roots. */

import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PACKAGE_ROOT = path.resolve(SCRIPT_DIR, "../..");
const dashboardRequire = createRequire(
  path.join(PACKAGE_ROOT, "apps/runtime-dashboard/package.json"),
);
const ts = dashboardRequire("typescript");

const SCHEMA_ID = "polisyos.atlas.ds18-time-semantics-scan.v1";
const SOURCE_ROOT = "apps/runtime-dashboard/src";
const GENERATED_MANIFEST = "architecture/generated_artifacts.toml";
const TEST_FILE_PATTERN = /\.(?:test|spec)\.(?:ts|tsx)$/u;
const STORY_FILE_PATTERN = /\.stories\.(?:ts|tsx)$/u;
const HTML_TEMPLATE_PATTERN =
  /<(?:!doctype\s+html|html|body|article|section|table|div|foreignObject)(?:\s|>)/iu;
const SVG_TEMPLATE_PATTERN = /<svg(?:\s|>)/iu;
const SERVER_RENDER_CALLS = new Set([
  "render",
  "renderToPipeableStream",
  "renderToReadableStream",
  "renderToStaticMarkup",
  "renderToString",
]);
const SATORI_CALLS = new Set(["satori"]);

function sha256(value) {
  return `sha256:${createHash("sha256").update(value).digest("hex")}`;
}

function parseArgs(argv) {
  let repoRoot = PACKAGE_ROOT;
  let json = false;
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--repo-root") {
      const value = argv[index + 1];
      if (!value) {
        throw new TypeError("--repo-root requires a path");
      }
      repoRoot = path.resolve(value);
      index += 1;
    } else if (arg === "--json") {
      json = true;
    } else {
      throw new TypeError(`unknown argument: ${arg}`);
    }
  }
  return { json, repoRoot };
}

function registeredGeneratedOutputs(repoRoot) {
  const manifestPath = path.join(repoRoot, GENERATED_MANIFEST);
  const manifest = readFileSync(manifestPath, "utf8");
  const outputs = new Set();
  const arrays = manifest.matchAll(/\boutputs\s*=\s*\[([\s\S]*?)\]/gu);
  for (const match of arrays) {
    for (const quoted of match[1].matchAll(/"([^"]+)"/gu)) {
      outputs.add(quoted[1]);
    }
  }
  return outputs;
}

function walkFiles(directory) {
  const files = [];
  for (const name of readdirSync(directory).sort()) {
    const absolute = path.join(directory, name);
    const stats = statSync(absolute);
    if (stats.isDirectory()) {
      files.push(...walkFiles(absolute));
    } else if (stats.isFile()) {
      files.push(absolute);
    }
  }
  return files;
}

function exclusionKind(relativePath, generatedOutputs) {
  const normalized = relativePath.split(path.sep).join("/");
  const sourceRelative = normalized.slice(`${SOURCE_ROOT}/`.length);
  const parts = sourceRelative.split("/");
  const basename = parts.at(-1) ?? "";
  if (
    parts
      .slice(0, -1)
      .some((part) => ["__tests__", "test", "tests"].includes(part))
  ) {
    return "test_directory";
  }
  if (TEST_FILE_PATTERN.test(basename)) {
    return "test_file";
  }
  if (STORY_FILE_PATTERN.test(basename)) {
    return "story_file";
  }
  if (generatedOutputs.has(normalized)) {
    return "registered_generated_output";
  }
  return null;
}

function nodeName(node, sourceFile) {
  if (node.name && typeof node.name.getText === "function") {
    return node.name.getText(sourceFile);
  }
  return null;
}

function componentIdentity(node, sourceFile) {
  let current = node;
  while (current && current !== sourceFile) {
    if (ts.isFunctionDeclaration(current) && current.name) {
      return current.name.text;
    }
    if (
      (ts.isMethodDeclaration(current) ||
        ts.isGetAccessorDeclaration(current) ||
        ts.isSetAccessorDeclaration(current)) &&
      current.name
    ) {
      return current.name.getText(sourceFile);
    }
    if (
      (ts.isArrowFunction(current) || ts.isFunctionExpression(current)) &&
      ts.isVariableDeclaration(current.parent)
    ) {
      return current.parent.name.getText(sourceFile);
    }
    if (ts.isPropertyAssignment(current) && current.name) {
      return current.name.getText(sourceFile);
    }
    current = current.parent;
  }
  return "<module>";
}

function hasJsxAncestor(node) {
  let current = node.parent;
  while (current) {
    if (
      ts.isJsxElement(current) ||
      ts.isJsxFragment(current) ||
      ts.isJsxSelfClosingElement(current)
    ) {
      return true;
    }
    current = current.parent;
  }
  return false;
}

function descendantCounts(node) {
  let epochContextReadCount = 0;
  let epochSemanticsLabelRenderCount = 0;
  let epochSemanticsProviderRenderCount = 0;
  let epochSemanticsPropCount = 0;
  function visit(current) {
    if (
      ts.isJsxOpeningElement(current) ||
      ts.isJsxSelfClosingElement(current)
    ) {
      const tag = current.tagName.getText();
      if (tag === "TimeSemanticsLabel") {
        epochSemanticsLabelRenderCount += 1;
      }
      if (tag === "EpochSemanticsProvider") {
        epochSemanticsProviderRenderCount += 1;
      }
      for (const property of current.attributes.properties) {
        if (
          ts.isJsxAttribute(property) &&
          property.name.text === "epochSemantics"
        ) {
          epochSemanticsPropCount += 1;
        }
      }
    }
    if (
      ts.isCallExpression(current) &&
      ts.isIdentifier(current.expression) &&
      current.expression.text === "useEpochSemantics"
    ) {
      epochContextReadCount += 1;
    }
    ts.forEachChild(current, visit);
  }
  visit(node);
  return {
    epoch_context_read_count: epochContextReadCount,
    epoch_semantics_prop_count: epochSemanticsPropCount,
    epoch_semantics_provider_render_count: epochSemanticsProviderRenderCount,
    time_semantics_label_render_count: epochSemanticsLabelRenderCount,
  };
}

function callName(expression) {
  if (ts.isIdentifier(expression)) {
    return expression.text;
  }
  if (ts.isPropertyAccessExpression(expression)) {
    return expression.name.text;
  }
  return "";
}

function rootKind(node, sourceFile) {
  if (
    (ts.isJsxElement(node) ||
      ts.isJsxFragment(node) ||
      ts.isJsxSelfClosingElement(node)) &&
    !hasJsxAncestor(node)
  ) {
    return "jsx";
  }
  if (
    ts.isTaggedTemplateExpression(node) ||
    ts.isTemplateExpression(node) ||
    ts.isNoSubstitutionTemplateLiteral(node)
  ) {
    const text = node.getText(sourceFile);
    if (SVG_TEMPLATE_PATTERN.test(text)) {
      return "svg_template";
    }
    if (HTML_TEMPLATE_PATTERN.test(text)) {
      return "html_template";
    }
  }
  if (ts.isCallExpression(node)) {
    const name = callName(node.expression);
    const expressionText = node.expression.getText(sourceFile);
    if (
      name === "createElement" &&
      (ts.isIdentifier(node.expression) ||
        expressionText === "React.createElement")
    ) {
      return "react_create_element";
    }
    if (SERVER_RENDER_CALLS.has(name)) {
      return "server_render";
    }
    if (SATORI_CALLS.has(name)) {
      return "satori_render";
    }
    if (name === "cloneNode") {
      return "dom_clone";
    }
    if (name === "serializeToString") {
      return "dom_serialize";
    }
    if (["toBlob", "toDataURL"].includes(name)) {
      return "raster_export";
    }
    if (name === "print") {
      return "print_root";
    }
  }
  if (
    ts.isPropertyAccessExpression(node) &&
    ["innerHTML", "outerHTML"].includes(node.name.text)
  ) {
    return "dom_serialize";
  }
  return null;
}

function inventorySource(relativePath, source) {
  const kind = relativePath.endsWith(".tsx")
    ? ts.ScriptKind.TSX
    : ts.ScriptKind.TS;
  const sourceFile = ts.createSourceFile(
    relativePath,
    source,
    ts.ScriptTarget.Latest,
    true,
    kind,
  );
  const roots = [];
  const seen = new Set();
  function visit(node) {
    const kindName = rootKind(node, sourceFile);
    if (kindName) {
      const start = node.getStart(sourceFile);
      const location = sourceFile.getLineAndCharacterOfPosition(start);
      const identity = componentIdentity(node, sourceFile);
      const rootId = `${identity.replace(/[^a-zA-Z0-9_.:-]+/gu, "-")}:${kindName}:${location.line + 1}:${location.character + 1}`;
      if (!seen.has(rootId)) {
        seen.add(rootId);
        roots.push({
          column: location.character + 1,
          component_identity: identity,
          kind: kindName,
          line: location.line + 1,
          root_id: rootId,
          root_source_sha256: sha256(node.getText(sourceFile)),
          ...descendantCounts(node),
        });
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  roots.sort(
    (left, right) =>
      left.line - right.line ||
      left.column - right.column ||
      left.kind.localeCompare(right.kind) ||
      left.root_id.localeCompare(right.root_id),
  );
  return roots;
}

function scan(repoRoot) {
  const generatedOutputs = registeredGeneratedOutputs(repoRoot);
  const absoluteSourceRoot = path.join(repoRoot, SOURCE_ROOT);
  const files = [];
  const exclusions = [];
  for (const absolute of walkFiles(absoluteSourceRoot)) {
    if (!absolute.endsWith(".ts") && !absolute.endsWith(".tsx")) {
      continue;
    }
    const relativePath = path
      .relative(repoRoot, absolute)
      .split(path.sep)
      .join("/");
    const excludedAs = exclusionKind(relativePath, generatedOutputs);
    if (excludedAs) {
      exclusions.push({ kind: excludedAs, path: relativePath });
      continue;
    }
    const source = readFileSync(absolute, "utf8");
    const roots = inventorySource(relativePath, source);
    files.push({
      path: relativePath,
      receipt_kind:
        roots.length > 0 ? "render_roots_complete" : "no_render_root",
      roots,
      source_sha256: sha256(source),
    });
  }
  files.sort((left, right) => left.path.localeCompare(right.path));
  exclusions.sort((left, right) => left.path.localeCompare(right.path));
  const fileManifest = files.map(({ path: filePath, source_sha256 }) => [
    filePath,
    source_sha256,
  ]);
  const rootManifest = files.flatMap((file) =>
    file.roots.map((root) => [
      file.path,
      root.root_id,
      root.root_source_sha256,
    ]),
  );
  return {
    schema_id: SCHEMA_ID,
    exclusion_policy: {
      generated_manifest: GENERATED_MANIFEST,
      kinds: [
        "registered_generated_output",
        "story_file",
        "test_directory",
        "test_file",
      ],
    },
    excluded_file_count: exclusions.length,
    exclusions,
    file_count: files.length,
    file_manifest_sha256: sha256(JSON.stringify(fileManifest)),
    files,
    root_count: rootManifest.length,
    root_manifest_sha256: sha256(JSON.stringify(rootManifest)),
    source_root: SOURCE_ROOT,
  };
}

try {
  const { json, repoRoot } = parseArgs(process.argv.slice(2));
  const result = scan(repoRoot);
  if (!json) {
    process.stderr.write("decision_time_semantics_scan requires --json\n");
    process.exitCode = 2;
  } else {
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  }
} catch (error) {
  process.stderr.write(
    `${error instanceof Error ? error.message : String(error)}\n`,
  );
  process.exitCode = 1;
}
