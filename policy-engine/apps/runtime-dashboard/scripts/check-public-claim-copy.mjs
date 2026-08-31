#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, extname, relative, resolve, sep } from "node:path";

import ts from "typescript";

const APP_ROUTES_SOURCE = "src/app/routes/routes.tsx";
const TRUST_ROUTE_SOURCE = "src/features/trust/routes.public.tsx";
const TRUST_COPY_SOURCE = "src/features/trust/copy/useTrustCopy.ts";
const TRUST_ARTIFACT_PATH = "/atlas/trust-claim-posture.v1.json";
const ACCESSIBLE_COPY_ATTRIBUTES = new Set([
  "alt",
  "aria-label",
  "placeholder",
  "title",
]);
const TEST_SOURCE_PATTERN =
  /(?:^|\/)(?:__tests__|test)(?:\/|$)|\.(?:spec|stories|test)\.tsx$/u;
const LETTER_OR_NUMBER = /[\p{L}\p{N}]/u;
const ALLOWED_BRAND_LITERAL = "PolicyOS";

const ALLOWED_ARTIFACT_FIELDS = new Set([
  "antiRole.display_label",
  "antiRole.role",
  "binding.coordinate.column",
  "binding.coordinate.field_name",
  "binding.coordinate.line",
  "binding.coordinate.path",
  "binding.coordinate.symbol",
  "binding.coordinate.use_kind",
  "binding.evidence_bindings",
  "binding.resolution",
  "binding.review_due",
  "binding.review_on",
  "binding.source_state",
  "binding.subject",
  "document.limitation_refs",
  "document.path",
  "document.source_as_of",
  "evidence.establishment_class",
  "evidence.ref",
  "evidence.verifier_ref",
  "failure.issue_signature",
  "failure.test_id",
  "group.claim_ids",
  "group.group_id",
  "groupsByClaim.get",
  "receipt.failures",
  "receipt.limitation_refs",
  "receipt.path",
  "receipt.source_as_of",
  "register.admitted_verifiers",
  "register.identity_boundary.anti_roles",
  "register.identity_boundary.identity_statement",
  "register.identity_boundary.identity_statement_start_line",
  "register.identity_boundary.path",
  "register.payload_digest",
  "register.projection_groups",
  "register.register_as_of",
  "register.rule_version",
  "register.schema_version",
  "register.source_set_digest",
  "row.authoritative_for",
  "row.blocker_codes",
  "row.claim_id",
  "row.effective_state",
  "row.limitations",
  "row.may_not_use_for",
  "row.review_due",
  "row.review_on",
  "row.source_as_of",
  "row.source_bindings",
  "row.subject",
  "verifier.establishment_class",
  "verifier.provenance_ref",
  "verifier.ref",
]);
const ALLOWED_ARTIFACT_VALUES = new Set(["blocker", "limitation"]);
const ARTIFACT_ROOTS = new Set(
  [...ALLOWED_ARTIFACT_FIELDS].map((field) => field.split(".", 1)[0]),
);
const COLLECTION_METHODS = new Set([
  "filter",
  "flatMap",
  "includes",
  "join",
  "map",
]);

function parseArguments(argv) {
  let root = process.cwd();
  let json = false;
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--root") {
      const value = argv[index + 1];
      if (!value) throw new TypeError("--root requires a path");
      root = resolve(value);
      index += 1;
    } else if (argument === "--json") {
      json = true;
    } else {
      throw new TypeError(`unknown argument: ${argument}`);
    }
  }
  return { json, root: resolve(root) };
}

const options = parseArguments(process.argv.slice(2));
const violations = [];
const expressions = [];
const artifactFields = new Set();
let admittedTrustCopyKeys = new Set();

function normalizePath(path) {
  return path.split(sep).join("/");
}

function absolutePath(relativePath) {
  return resolve(options.root, relativePath);
}

function addViolation(code, path, detail, line = 1) {
  violations.push({ code, detail, line, path });
}

function readSource(relativePath) {
  return readFileSync(absolutePath(relativePath), "utf8");
}

function parseSource(relativePath) {
  const source = readSource(relativePath);
  const kind = relativePath.endsWith(".tsx")
    ? ts.ScriptKind.TSX
    : ts.ScriptKind.TS;
  return ts.createSourceFile(
    relativePath,
    source,
    ts.ScriptTarget.Latest,
    true,
    kind,
  );
}

function lineOf(sourceFile, node) {
  return (
    sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
  );
}

function unwrap(expression) {
  let current = expression;
  while (
    current &&
    (ts.isAsExpression(current) ||
      ts.isParenthesizedExpression(current) ||
      ts.isSatisfiesExpression(current) ||
      ts.isTypeAssertionExpression(current))
  ) {
    current = current.expression;
  }
  return current;
}

function findVariable(sourceFile, name) {
  let found = null;
  function visit(node) {
    if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      node.name.text === name
    ) {
      found = node;
      return;
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return found;
}

function stringArray(sourceFile, name) {
  const declaration = findVariable(sourceFile, name);
  const initializer = declaration?.initializer
    ? unwrap(declaration.initializer)
    : null;
  if (!initializer || !ts.isArrayLiteralExpression(initializer)) {
    addViolation(
      "copy_denominator_missing",
      sourceFile.fileName,
      `${name} must be a literal array`,
      declaration ? lineOf(sourceFile, declaration) : 1,
    );
    return [];
  }
  const values = [];
  for (const element of initializer.elements) {
    if (!ts.isStringLiteral(element)) {
      addViolation(
        "copy_denominator_dynamic",
        sourceFile.fileName,
        `${name} contains a non-literal member`,
        lineOf(sourceFile, element),
      );
      continue;
    }
    values.push(element.text);
  }
  return values;
}

function importSpecifiers(sourceFile) {
  const specifiers = [];
  function visit(node) {
    if (
      ts.isImportDeclaration(node) &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      const clause = node.importClause;
      const onlyNamedTypes =
        clause?.namedBindings &&
        ts.isNamedImports(clause.namedBindings) &&
        clause.namedBindings.elements.length > 0 &&
        clause.namedBindings.elements.every((element) => element.isTypeOnly);
      if (clause?.isTypeOnly || onlyNamedTypes) return;
      specifiers.push(node.moduleSpecifier.text);
    } else if (
      ts.isExportDeclaration(node) &&
      !node.isTypeOnly &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      specifiers.push(node.moduleSpecifier.text);
    } else if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      specifiers.push(node.arguments[0].text);
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return specifiers;
}

function resolveLocalImport(fromPath, specifier) {
  let stem;
  if (specifier.startsWith("@/")) {
    stem = `src/${specifier.slice(2)}`;
  } else if (specifier.startsWith(".")) {
    stem = normalizePath(resolve(options.root, dirname(fromPath), specifier));
    stem = normalizePath(relative(options.root, stem));
  } else {
    return null;
  }
  const candidates = extname(stem)
    ? [stem]
    : [
        `${stem}.ts`,
        `${stem}.tsx`,
        `${stem}.json`,
        `${stem}/index.ts`,
        `${stem}/index.tsx`,
      ];
  return (
    candidates.find((candidate) => existsSync(absolutePath(candidate))) ?? null
  );
}

function deriveImportClosure() {
  const pending = [TRUST_ROUTE_SOURCE];
  const local = new Set();
  const external = new Set();
  while (pending.length > 0) {
    const current = pending.shift();
    if (local.has(current)) continue;
    local.add(current);
    if (current.endsWith(".json")) continue;
    const sourceFile = parseSource(current);
    for (const specifier of importSpecifiers(sourceFile)) {
      const resolved = resolveLocalImport(current, specifier);
      if (resolved) {
        if (!local.has(resolved)) pending.push(resolved);
      } else if (specifier.startsWith(".") || specifier.startsWith("@/")) {
        addViolation(
          "unresolved_local_import",
          current,
          `cannot resolve ${specifier}`,
        );
      } else {
        external.add(specifier);
      }
    }
  }
  return {
    externalModules: [...external].sort(),
    localPaths: [...local].sort(),
  };
}

function verifyRouteConsumption() {
  const sourceFile = parseSource(APP_ROUTES_SOURCE);
  let imported = false;
  for (const statement of sourceFile.statements) {
    if (
      ts.isImportDeclaration(statement) &&
      ts.isStringLiteral(statement.moduleSpecifier) &&
      statement.moduleSpecifier.text === "@/features/trust/routes.public"
    ) {
      const elements = statement.importClause?.namedBindings;
      imported =
        !!elements &&
        ts.isNamedImports(elements) &&
        elements.elements.some((element) => element.name.text === "trustRoute");
    }
  }
  const appRoutes = findVariable(sourceFile, "APP_ROUTES");
  let consumed = false;
  if (appRoutes?.initializer) {
    function visit(node) {
      if (ts.isIdentifier(node) && node.text === "trustRoute") consumed = true;
      ts.forEachChild(node, visit);
    }
    visit(appRoutes.initializer);
  }
  if (!imported || !consumed) {
    addViolation(
      "trust_route_not_consumed",
      APP_ROUTES_SOURCE,
      "APP_ROUTES must consume the named trustRoute export",
    );
  }

  const routeSource = parseSource(TRUST_ROUTE_SOURCE);
  const trustRoute = findVariable(routeSource, "trustRoute");
  const handle = findVariable(routeSource, "trustRouteHandle");
  const routeText = trustRoute?.initializer?.getText(routeSource) ?? "";
  const handleText = handle?.initializer?.getText(routeSource) ?? "";
  if (!/\bpath\s*:\s*["']trust["']/u.test(routeText)) {
    addViolation(
      "trust_route_path_drift",
      TRUST_ROUTE_SOURCE,
      "trustRoute must retain the literal path trust",
    );
  }
  if (!/buildHref\s*:\s*\(\)\s*=>\s*["']\/trust["']/u.test(handleText)) {
    addViolation(
      "trust_route_href_drift",
      TRUST_ROUTE_SOURCE,
      "trustRouteHandle must build the literal /trust href",
    );
  }
}

function trackedProductionTsx() {
  const completed = spawnSync(
    "git",
    ["-C", options.root, "ls-files", "--", "src/**/*.tsx"],
    { encoding: "utf8" },
  );
  if (completed.status !== 0) {
    addViolation(
      "tracked_source_census_failed",
      "src",
      completed.stderr.trim() || "git ls-files failed",
    );
    return [];
  }
  return completed.stdout
    .split(/\r?\n/u)
    .filter(Boolean)
    .map(normalizePath)
    .filter((path) => !TEST_SOURCE_PATTERN.test(path))
    .sort();
}

function jsxAttribute(node, name) {
  const attribute = node.attributes.properties.find(
    (property) => ts.isJsxAttribute(property) && property.name.text === name,
  );
  return attribute && ts.isJsxAttribute(attribute) ? attribute : null;
}

function literalJsxAttribute(attribute) {
  if (!attribute?.initializer) return null;
  if (ts.isStringLiteral(attribute.initializer))
    return attribute.initializer.text;
  if (
    ts.isJsxExpression(attribute.initializer) &&
    attribute.initializer.expression &&
    ts.isStringLiteral(attribute.initializer.expression)
  ) {
    return attribute.initializer.expression.text;
  }
  return null;
}

function translationKeyInLink(node) {
  let key = null;
  function visit(candidate) {
    if (
      ts.isCallExpression(candidate) &&
      ts.isIdentifier(candidate.expression) &&
      candidate.expression.text === "t" &&
      candidate.arguments.length === 1 &&
      ts.isStringLiteral(candidate.arguments[0])
    ) {
      key = candidate.arguments[0].text;
    }
    ts.forEachChild(candidate, visit);
  }
  visit(node);
  return key;
}

function deriveInboundLinks(paths) {
  const links = [];
  for (const path of paths) {
    const sourceFile = parseSource(path);
    function visit(node) {
      if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
        const destination =
          literalJsxAttribute(jsxAttribute(node, "to")) ??
          literalJsxAttribute(jsxAttribute(node, "href"));
        if (destination === "/trust") {
          const parent = ts.isJsxOpeningElement(node) ? node.parent : node;
          const copyKey = translationKeyInLink(parent);
          if (copyKey !== "landing.trustPosture") {
            addViolation(
              "trust_inbound_copy_unowned",
              path,
              "literal /trust links must use landing.trustPosture",
              lineOf(sourceFile, node),
            );
          }
          links.push({ copy_key: copyKey, destination, path });
        }
      }
      ts.forEachChild(node, visit);
    }
    visit(sourceFile);
  }
  return links.sort((left, right) =>
    `${left.path}\0${left.destination}`.localeCompare(
      `${right.path}\0${right.destination}`,
    ),
  );
}

function flattenStringLeaves(value, prefix = "") {
  const leaves = [];
  if (!value || typeof value !== "object" || Array.isArray(value))
    return leaves;
  for (const key of Object.keys(value).sort()) {
    const next = prefix ? `${prefix}.${key}` : key;
    if (typeof value[key] === "string") leaves.push(next);
    else leaves.push(...flattenStringLeaves(value[key], next));
  }
  return leaves;
}

function deriveLocaleCopy() {
  const copySource = parseSource(TRUST_COPY_SOURCE);
  const localeSource = parseSource("src/shared/i18n/locale.ts");
  const copyKeys = stringArray(copySource, "TRUST_COPY_KEYS");
  const audienceKeys = stringArray(copySource, "TRUST_AUDIENCE_KEYS");
  const activeLocales = stringArray(localeSource, "SUPPORTED_LOCALES");
  const expectedLeaves = [
    ...copyKeys,
    ...audienceKeys.map((key) => `audience.${key}`),
  ].sort();
  let commonLeaves = null;
  for (const locale of activeLocales) {
    const path = `src/shared/i18n/locales/${locale}.json`;
    let payload;
    try {
      payload = JSON.parse(readSource(path));
    } catch (error) {
      addViolation("locale_catalog_invalid", path, String(error));
      continue;
    }
    const leaves = flattenStringLeaves(payload.trust).sort();
    if (JSON.stringify(leaves) !== JSON.stringify(expectedLeaves)) {
      const missing = expectedLeaves.filter((key) => !leaves.includes(key));
      const extra = leaves.filter((key) => !expectedLeaves.includes(key));
      addViolation(
        "trust_locale_denominator_drift",
        path,
        `missing=${JSON.stringify(missing)} extra=${JSON.stringify(extra)}`,
      );
    }
    if (commonLeaves === null) commonLeaves = leaves;
    else if (JSON.stringify(commonLeaves) !== JSON.stringify(leaves)) {
      addViolation(
        "trust_locale_parity_drift",
        path,
        "active locale trust leaves differ",
      );
    }
    const landing = payload.landing?.trustPosture;
    if (typeof landing !== "string" || landing.length === 0) {
      addViolation(
        "trust_inbound_locale_missing",
        path,
        "landing.trustPosture must be a non-empty string",
      );
    }
  }
  return {
    activeLocales,
    audienceKeys,
    copyKeys,
    leafKeys: expectedLeaves,
  };
}

function validatePostureArtifact() {
  const relativePath = `public${TRUST_ARTIFACT_PATH}`;
  let payload;
  try {
    payload = JSON.parse(readSource(relativePath));
  } catch (error) {
    addViolation("posture_artifact_unreadable", relativePath, String(error));
    return;
  }
  if (
    payload.schema_version !== "policyos.trust.claim_posture_register.v1" ||
    !Array.isArray(payload.claims) ||
    payload.claims.length === 0
  ) {
    addViolation(
      "posture_artifact_not_strict_source",
      relativePath,
      "the trust resource must be a non-empty v1 claim-posture register",
    );
  }
}

function propertyChain(node) {
  const segments = [];
  let current = node;
  while (ts.isPropertyAccessExpression(current)) {
    segments.unshift(current.name.text);
    current = current.expression;
  }
  if (!ts.isIdentifier(current)) return null;
  segments.unshift(current.text);
  return segments;
}

function normalizedArtifactChain(node) {
  const segments = propertyChain(node);
  if (!segments || !ARTIFACT_ROOTS.has(segments[0])) return null;
  if (COLLECTION_METHODS.has(segments.at(-1))) segments.pop();
  return segments.join(".");
}

function recordExpression(sourceFile, node, kind, value) {
  expressions.push({
    kind,
    line: lineOf(sourceFile, node),
    path: sourceFile.fileName,
    value,
  });
}

function auditVisibleExpression(sourceFile, expression) {
  function visit(node) {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
      if (node.expression.text === "tTrust") {
        const key = node.arguments[0];
        if (node.arguments.length !== 1 || !key || !ts.isStringLiteral(key)) {
          addViolation(
            "dynamic_trust_translation_key",
            sourceFile.fileName,
            "tTrust requires one literal audited key",
            lineOf(sourceFile, node),
          );
        } else {
          if (!admittedTrustCopyKeys.has(key.text)) {
            addViolation(
              "foreign_trust_translation_key",
              sourceFile.fileName,
              `tTrust key is outside TRUST_COPY_KEYS: ${key.text}`,
              lineOf(sourceFile, node),
            );
          } else {
            recordExpression(sourceFile, node, "locale", `trust.${key.text}`);
          }
        }
        return;
      }
      if (node.expression.text === "tTrustAudience") {
        if (
          node.arguments.length !== 1 ||
          !ts.isIdentifier(node.arguments[0])
        ) {
          addViolation(
            "dynamic_trust_audience_key",
            sourceFile.fileName,
            "tTrustAudience requires one typed audience identifier",
            lineOf(sourceFile, node),
          );
        } else {
          recordExpression(
            sourceFile,
            node,
            "locale",
            "trust.audience.<typed>",
          );
        }
        return;
      }
      if (node.expression.text === "t" || node.expression.text === "rich") {
        addViolation(
          "foreign_or_dynamic_translation_key",
          sourceFile.fileName,
          `${node.expression.text}(...) bypasses the trust-copy owner`,
          lineOf(sourceFile, node),
        );
        return;
      }
    }

    if (
      (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) &&
      LETTER_OR_NUMBER.test(node.text) &&
      node.text !== ALLOWED_BRAND_LITERAL
    ) {
      addViolation(
        "raw_claim_copy",
        sourceFile.fileName,
        `visible literal is outside the posture artifact: ${JSON.stringify(node.text)}`,
        lineOf(sourceFile, node),
      );
    }

    if (ts.isPropertyAccessExpression(node)) {
      const parent = node.parent;
      if (
        !ts.isPropertyAccessExpression(parent) ||
        parent.expression !== node
      ) {
        const chain = normalizedArtifactChain(node);
        if (chain) {
          if (!ALLOWED_ARTIFACT_FIELDS.has(chain)) {
            addViolation(
              "unadmitted_posture_field",
              sourceFile.fileName,
              `visible artifact expression is not in the audited denominator: ${chain}`,
              lineOf(sourceFile, node),
            );
          } else {
            artifactFields.add(chain);
            recordExpression(sourceFile, node, "artifact_field", chain);
          }
        }
      }
    }

    ts.forEachChild(node, visit);
  }

  if (
    ts.isIdentifier(expression) &&
    ALLOWED_ARTIFACT_VALUES.has(expression.text)
  ) {
    artifactFields.add(expression.text);
    recordExpression(sourceFile, expression, "artifact_field", expression.text);
    return;
  }
  visit(expression);
}

function containsJsx(expression) {
  let found = false;
  function visit(node) {
    if (
      ts.isJsxElement(node) ||
      ts.isJsxFragment(node) ||
      ts.isJsxSelfClosingElement(node)
    ) {
      found = true;
      return;
    }
    ts.forEachChild(node, visit);
  }
  visit(expression);
  return found;
}

function auditTrustRenderers(localPaths) {
  for (const path of localPaths) {
    if (!path.startsWith("src/features/trust/") || !path.endsWith(".tsx")) {
      continue;
    }
    const sourceFile = parseSource(path);
    function visit(node) {
      if (ts.isJsxText(node)) {
        const visible = node.text.replace(/\s+/gu, " ").trim();
        if (
          visible &&
          LETTER_OR_NUMBER.test(visible) &&
          visible !== ALLOWED_BRAND_LITERAL
        ) {
          addViolation(
            "raw_claim_copy",
            path,
            `visible JSX text is outside the posture artifact: ${JSON.stringify(visible)}`,
            lineOf(sourceFile, node),
          );
        } else if (visible) {
          recordExpression(sourceFile, node, "format_literal", visible);
        }
      } else if (
        ts.isJsxExpression(node) &&
        !ts.isJsxAttribute(node.parent) &&
        node.expression &&
        !containsJsx(node.expression)
      ) {
        auditVisibleExpression(sourceFile, node.expression);
      } else if (
        ts.isJsxAttribute(node) &&
        ACCESSIBLE_COPY_ATTRIBUTES.has(node.name.text)
      ) {
        if (node.initializer && ts.isStringLiteral(node.initializer)) {
          if (
            LETTER_OR_NUMBER.test(node.initializer.text) &&
            node.initializer.text !== ALLOWED_BRAND_LITERAL
          ) {
            addViolation(
              "raw_claim_copy",
              path,
              `${node.name.text} literal is outside the posture artifact`,
              lineOf(sourceFile, node),
            );
          }
        } else if (
          node.initializer &&
          ts.isJsxExpression(node.initializer) &&
          node.initializer.expression
        ) {
          auditVisibleExpression(sourceFile, node.initializer.expression);
        }
      }
      ts.forEachChild(node, visit);
    }
    visit(sourceFile);
  }
}

function validateTrustWrapper(copyKeys, audienceKeys) {
  const sourceFile = parseSource(TRUST_COPY_SOURCE);
  const allowedTemplates = new Set([
    "trust.${key}",
    "trust.audience.${audience}",
  ]);
  function visit(node) {
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "t"
    ) {
      const argument = node.arguments[0];
      const value = argument?.getText(sourceFile).replaceAll("`", "");
      if (
        node.arguments.length !== 1 ||
        !value ||
        !allowedTemplates.has(value)
      ) {
        addViolation(
          "trust_copy_wrapper_unbounded",
          TRUST_COPY_SOURCE,
          "the trust-copy wrapper may resolve only its two typed namespaces",
          lineOf(sourceFile, node),
        );
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  if (new Set(copyKeys).size !== copyKeys.length) {
    addViolation(
      "trust_copy_key_duplicate",
      TRUST_COPY_SOURCE,
      "TRUST_COPY_KEYS contains a duplicate",
    );
  }
  if (new Set(audienceKeys).size !== audienceKeys.length) {
    addViolation(
      "trust_audience_key_duplicate",
      TRUST_COPY_SOURCE,
      "TRUST_AUDIENCE_KEYS contains a duplicate",
    );
  }
}

verifyRouteConsumption();
validatePostureArtifact();
const closure = deriveImportClosure();
const trackedTsx = trackedProductionTsx();
const inboundLinks = deriveInboundLinks(trackedTsx);
const localeCopy = deriveLocaleCopy();
admittedTrustCopyKeys = new Set(localeCopy.copyKeys);
validateTrustWrapper(localeCopy.copyKeys, localeCopy.audienceKeys);
auditTrustRenderers(closure.localPaths);

const fileTypeCounts = {};
for (const path of closure.localPaths) {
  const extension = extname(path) || "<none>";
  fileTypeCounts[extension] = (fileTypeCounts[extension] ?? 0) + 1;
}

violations.sort((left, right) =>
  `${left.path}\0${String(left.line).padStart(8, "0")}\0${left.code}\0${left.detail}`.localeCompare(
    `${right.path}\0${String(right.line).padStart(8, "0")}\0${right.code}\0${right.detail}`,
  ),
);
expressions.sort((left, right) =>
  `${left.path}\0${String(left.line).padStart(8, "0")}\0${left.kind}\0${left.value}`.localeCompare(
    `${right.path}\0${String(right.line).padStart(8, "0")}\0${right.kind}\0${right.value}`,
  ),
);

const report = {
  schema_version: "policyos.public_claim_copy_check.v1",
  status: violations.length === 0 ? "pass" : "fail",
  route: {
    app_routes_source: APP_ROUTES_SOURCE,
    consumed_export: "trustRoute",
    path: "/trust",
    route_export_source: TRUST_ROUTE_SOURCE,
  },
  import_closure: {
    external_module_count: closure.externalModules.length,
    external_modules: closure.externalModules,
    local_file_type_counts: Object.fromEntries(
      Object.entries(fileTypeCounts).sort(([left], [right]) =>
        left.localeCompare(right),
      ),
    ),
    local_path_count: closure.localPaths.length,
    local_paths: closure.localPaths,
  },
  inbound_links: {
    links: inboundLinks,
    tracked_production_tsx_count: trackedTsx.length,
    tracked_production_tsx_paths: trackedTsx,
  },
  locale_copy: {
    active_locales: localeCopy.activeLocales,
    leaf_count: localeCopy.leafKeys.length,
    leaf_keys: localeCopy.leafKeys,
    source_language_authority: "not_established",
  },
  claim_copy_inventory: {
    artifact_fields: [...artifactFields].sort(),
    expression_count: expressions.length,
    expressions,
  },
  artifact: {
    path: TRUST_ARTIFACT_PATH,
    admission: "strict_runtime_schema",
    translation_truth: "not_established",
  },
  violations,
};

process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
process.exitCode = violations.length === 0 ? 0 : 1;
