import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

/**
 * DS16-C02 — the successor containment gate's analyzer.
 *
 * `mintedValueFindings` is C01's analyzer, MOVED here verbatim rather than
 * reimplemented: C01 wrote it inside its own spec, and C02 needs the identical
 * function over the real panel files. One analyzer, one home, two consumers —
 * `ds16SuccessorAuthority.test.ts` (C01's negative, over fixtures) and
 * `ds16SuccessorContainment.test.ts` (C02's gate, over production sources). A
 * second copy beside the first would be `P27`.
 *
 * The functions added for C02 are SEPARATE properties, deliberately not folded
 * into `mintedValueFindings`:
 *
 *   `mintedValueFindings`  — no value is computed locally.
 *   `refusalFindings`      — an absent value renders a typed refusal, never a
 *                            blank, a zero, or an inference.
 *   `renderedLabelKeys`    — the label channel's pinned key inventory (gap 2).
 *   `panelEmissionMode`    — contained vs bound, so the gate can SAY which
 *                            reason it is passing for (the vacuity trap).
 *   `mountGraphFindings`   — the cross-file mount census (gap 1).
 *
 * Keeping them separate is what lets C01's expectations stay byte-stable while
 * C02 adds properties; folding a new finding into `mintedValueFindings` would
 * have silently rewritten C01's proven-RED arrays.
 */

export const dashboardRoot = path.resolve(import.meta.dirname, "../../..");
export const sourceRoot = path.join(dashboardRoot, "src");
export const readinessPanelPath = path.join(
  sourceRoot,
  "features/runs/components/PublicSectorReadinessPanel.tsx",
);
export const scientificPanelPath = path.join(
  sourceRoot,
  "features/runs/components/ScientificDepthPanel.tsx",
);
export const runDetailLayoutPath = path.join(
  sourceRoot,
  "features/runs/routes/RunDetailLayout.tsx",
);
export const governanceTabPath = path.join(
  sourceRoot,
  "features/runs/routes/tabs/GovernanceTab.tsx",
);

export const PANEL_NAMES = new Set([
  "PublicSectorReadinessPanel",
  "ScientificDepthPanel",
]);

/**
 * The sanctioned producer surface.
 *
 * C05 added `useRunAuthorityValues`. The gate refused the rewired panel until this
 * line changed — which is the point: a panel cannot reach for a new producer without
 * someone widening this set on purpose, in a diff a reviewer sees.
 */
export const DEFAULT_PRODUCER_READS = [
  "useI18n",
  "useRunAuthorityValues",
] as const;

/**
 * The refusal the ancestor already pins. REFERENCED from
 * `readinessScientificContainment.test.ts`, never coined here: DS16 does not
 * own the i18n catalog (`shared/i18n/**` is DS6's exclusive territory), so the
 * gate may name this key but may not mint a new one.
 */
export const SANCTIONED_REFUSAL_KEY = "common.unavailable";

const ARITHMETIC_OPERATORS = new Set<ts.SyntaxKind>([
  ts.SyntaxKind.PlusToken,
  ts.SyntaxKind.MinusToken,
  ts.SyntaxKind.AsteriskToken,
  ts.SyntaxKind.AsteriskAsteriskToken,
  ts.SyntaxKind.SlashToken,
  ts.SyntaxKind.PercentToken,
]);

const THRESHOLD_OPERATORS = new Set<ts.SyntaxKind>([
  ts.SyntaxKind.LessThanToken,
  ts.SyntaxKind.LessThanEqualsToken,
  ts.SyntaxKind.GreaterThanToken,
  ts.SyntaxKind.GreaterThanEqualsToken,
  ts.SyntaxKind.EqualsEqualsToken,
  ts.SyntaxKind.EqualsEqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsToken,
  ts.SyntaxKind.ExclamationEqualsEqualsToken,
]);

export type SourceOverrides = Record<string, string>;

function parse(text: string, fileName: string) {
  return ts.createSourceFile(
    fileName,
    text,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
}

function calleeName(call: ts.CallExpression): string {
  return ts.isIdentifier(call.expression)
    ? call.expression.text
    : call.expression.getText();
}

function unaliasedImports(source: ts.SourceFile): Set<string> {
  const names = new Set<string>();
  for (const statement of source.statements) {
    if (!ts.isImportDeclaration(statement)) continue;
    const bindings = statement.importClause?.namedBindings;
    if (!bindings || !ts.isNamedImports(bindings)) continue;
    for (const element of bindings.elements) {
      if (element.propertyName === undefined) names.add(element.name.text);
    }
  }
  return names;
}

function traceableRoot(expression: ts.Expression): string | null {
  let current: ts.Node = expression;
  for (;;) {
    if (
      ts.isPropertyAccessExpression(current) ||
      ts.isElementAccessExpression(current)
    ) {
      current = current.expression;
      continue;
    }
    if (ts.isNonNullExpression(current) || ts.isParenthesizedExpression(current)) {
      current = current.expression;
      continue;
    }
    break;
  }
  return ts.isIdentifier(current) ? current.text : null;
}

/**
 * `producerCollection.map(item => ...)` — iteration, not computation.
 *
 * C05 forced this distinction. A panel that renders a served collection must walk it,
 * and a gate that refuses `.map` would push the loop into a helper the gate cannot see,
 * which is the ancestor's direct-helper corruption wearing a different hat. So iteration
 * over a value traceable to a producer is permitted, the callback parameter becomes a
 * producer root inside the callback, and every other rule keeps applying underneath —
 * a callback that computes is still caught.
 */
function producerIterationParameters(
  node: ts.Expression,
  roots: ReadonlySet<string>,
): string[] | null {
  if (
    !ts.isCallExpression(node) ||
    !ts.isPropertyAccessExpression(node.expression) ||
    node.expression.name.text !== "map" ||
    node.arguments.length !== 1
  ) {
    return null;
  }
  const source = traceableRoot(node.expression.expression);
  if (source === null || !roots.has(source)) return null;
  const callback = node.arguments[0];
  if (!ts.isArrowFunction(callback)) return null;
  const parameters: string[] = [];
  for (const parameter of callback.parameters) {
    if (ts.isIdentifier(parameter.name)) parameters.push(parameter.name.text);
    if (ts.isObjectBindingPattern(parameter.name)) {
      for (const element of parameter.name.elements) {
        if (ts.isIdentifier(element.name)) parameters.push(element.name.text);
      }
    }
  }
  return parameters;
}

function isLabelCall(node: ts.Expression, roots: ReadonlySet<string>): boolean {
  return (
    ts.isCallExpression(node) &&
    ts.isIdentifier(node.expression) &&
    roots.has(node.expression.text) &&
    node.arguments.length === 1 &&
    ts.isStringLiteral(node.arguments[0])
  );
}

function localComponentNames(source: ts.SourceFile): Set<string> {
  const names = new Set<string>();
  for (const statement of source.statements) {
    if (ts.isFunctionDeclaration(statement) && statement.name) {
      names.add(statement.name.text);
    }
    if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        if (ts.isIdentifier(declaration.name)) names.add(declaration.name.text);
      }
    }
  }
  return names;
}

function componentDeclaration(source: ts.SourceFile, componentName: string) {
  return source.statements.find(
    (statement): statement is ts.FunctionDeclaration =>
      ts.isFunctionDeclaration(statement) &&
      statement.name?.text === componentName,
  );
}

/** Producer roots: parameters, plus bindings destructured from producer reads. */
function producerRoots(
  declaration: ts.FunctionDeclaration,
  sanctioned: ReadonlySet<string>,
): { roots: Set<string>; reads: string[] } {
  const roots = new Set<string>();
  const reads: string[] = [];
  for (const parameter of declaration.parameters) {
    if (ts.isIdentifier(parameter.name)) roots.add(parameter.name.text);
    if (ts.isObjectBindingPattern(parameter.name)) {
      for (const element of parameter.name.elements) {
        if (ts.isIdentifier(element.name)) roots.add(element.name.text);
      }
    }
  }
  for (const statement of declaration.body?.statements ?? []) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const binding of statement.declarationList.declarations) {
      const initializer = binding.initializer;
      if (!initializer || !ts.isCallExpression(initializer)) continue;
      const callee = calleeName(initializer);
      if (sanctioned.has(callee)) reads.push(callee);
      if (ts.isObjectBindingPattern(binding.name)) {
        for (const element of binding.name.elements) {
          if (ts.isIdentifier(element.name)) roots.add(element.name.text);
        }
      } else if (ts.isIdentifier(binding.name)) {
        roots.add(binding.name.text);
      }
    }
  }
  return { reads, roots };
}

// ---------------------------------------------------------------------------
// C01's analyzer, moved verbatim. Do not fold new properties into this.
// ---------------------------------------------------------------------------

export function mintedValueFindings(
  text: string,
  componentName: string,
  producerReads: readonly string[] = DEFAULT_PRODUCER_READS,
): string[] {
  const source = parse(text, `${componentName}.tsx`);
  const declaration = componentDeclaration(source, componentName);
  if (!declaration?.body) return [`panel-missing:${componentName}`];

  const sanctioned = new Set(producerReads);
  const imported = unaliasedImports(source);
  const declared = localComponentNames(source);
  const findings = new Set<string>();
  const sanctionedCalls = new Set<ts.Node>();
  const roots = new Set<string>();

  for (const parameter of declaration.parameters) {
    if (ts.isIdentifier(parameter.name)) roots.add(parameter.name.text);
    if (ts.isObjectBindingPattern(parameter.name)) {
      for (const element of parameter.name.elements) {
        if (ts.isIdentifier(element.name)) roots.add(element.name.text);
      }
    }
  }

  for (const statement of declaration.body.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    if ((statement.declarationList.flags & ts.NodeFlags.Const) === 0) {
      findings.add("mutable-producer-binding");
    }
    for (const binding of statement.declarationList.declarations) {
      const initializer = binding.initializer;
      if (!initializer || !ts.isCallExpression(initializer)) continue;
      const callee = calleeName(initializer);
      sanctionedCalls.add(initializer);
      if (!sanctioned.has(callee)) {
        findings.add(`unsanctioned-producer-read:${callee}`);
      } else if (!imported.has(callee)) {
        findings.add(`unimported-producer-read:${callee}`);
      }
      // A prop handed to a producer read (`useX(runId)`) is not a computed argument.
      const computedArgument = initializer.arguments.some((argument) => {
        if (ts.isStringLiteral(argument)) return false;
        const argumentRoot = traceableRoot(argument);
        return argumentRoot === null || !roots.has(argumentRoot);
      });
      if (computedArgument) {
        findings.add(`computed-producer-argument:${callee}`);
      }
      if (ts.isObjectBindingPattern(binding.name)) {
        for (const element of binding.name.elements) {
          if (element.propertyName !== undefined) {
            findings.add("renamed-producer-binding");
          }
          if (ts.isIdentifier(element.name)) roots.add(element.name.text);
        }
      } else if (ts.isIdentifier(binding.name)) {
        roots.add(binding.name.text);
      }
    }
  }

  const classifyRendered = (expression: ts.Expression, slot: string) => {
    if (isLabelCall(expression, roots)) {
      sanctionedCalls.add(expression);
      return;
    }
    if (ts.isConditionalExpression(expression)) {
      findings.add(`local-conditional:${slot}`);
      return;
    }
    const iterationParameters = producerIterationParameters(expression, roots);
    if (iterationParameters !== null) {
      sanctionedCalls.add(expression);
      for (const parameter of iterationParameters) roots.add(parameter);
      return;
    }
    if (ts.isCallExpression(expression)) {
      findings.add(`local-call-in-render:${calleeName(expression)}`);
      return;
    }
    if (ts.isStringLiteral(expression) || ts.isNumericLiteral(expression)) {
      findings.add(`literal-value-rendered:${slot}`);
      return;
    }
    const root = traceableRoot(expression);
    if (root === null) {
      findings.add(`untraceable-render:${slot}`);
      return;
    }
    if (!roots.has(root)) {
      findings.add(`untraceable-render:${root}`);
    }
  };

  let returns = 0;
  const visit = (node: ts.Node) => {
    if (ts.isReturnStatement(node)) returns += 1;
    if (
      ts.isIfStatement(node) ||
      ts.isSwitchStatement(node) ||
      ts.isForStatement(node) ||
      ts.isForOfStatement(node) ||
      ts.isForInStatement(node) ||
      ts.isWhileStatement(node)
    ) {
      findings.add("local-control-flow");
    }
    if (ts.isBinaryExpression(node)) {
      if (ARITHMETIC_OPERATORS.has(node.operatorToken.kind)) {
        findings.add("local-arithmetic");
      }
      if (THRESHOLD_OPERATORS.has(node.operatorToken.kind)) {
        findings.add("local-threshold");
      }
    }
    if (ts.isRegularExpressionLiteral(node)) findings.add("local-regex");
    if (ts.isJsxSpreadAttribute(node)) findings.add("prop-spread");
    if (ts.isJsxText(node) && node.text.trim() !== "") {
      findings.add("literal-text-rendered");
    }
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = ts.isIdentifier(node.tagName)
        ? node.tagName.text
        : node.tagName.getText();
      if (/^[A-Z]/.test(tag) && !declared.has(tag)) {
        findings.add(`opaque-component-child:${tag}`);
      }
    }
    if (ts.isJsxExpression(node) && node.expression) {
      const slot =
        node.parent &&
        ts.isJsxAttribute(node.parent) &&
        ts.isIdentifier(node.parent.name)
          ? `attr:${node.parent.name.text}`
          : "child";
      classifyRendered(node.expression, slot);
    }
    ts.forEachChild(node, visit);
  };
  visit(declaration.body);

  if (returns > 1) findings.add("local-control-flow");

  const sweep = (node: ts.Node) => {
    if (ts.isCallExpression(node) && !sanctionedCalls.has(node)) {
      findings.add(`unbound-call:${calleeName(node)}`);
    }
    ts.forEachChild(node, sweep);
  };
  sweep(declaration.body);

  return [...findings].sort();
}

// ---------------------------------------------------------------------------
// C02 additions
// ---------------------------------------------------------------------------

export type PanelEmissionMode = "contained" | "bound" | "absent";

/**
 * Which reason the panel is passing for. The gate must SAY this, because
 * "emits nothing it did not receive" is trivially satisfied by a panel that
 * emits nothing at all — and both panels are stubs today.
 */
export function panelEmissionMode(
  text: string,
  componentName: string,
  producerReads: readonly string[] = DEFAULT_PRODUCER_READS,
): PanelEmissionMode {
  const source = parse(text, `${componentName}.tsx`);
  const declaration = componentDeclaration(source, componentName);
  if (!declaration?.body) return "absent";
  const { reads } = producerRoots(declaration, new Set(producerReads));
  return reads.some((read) => read !== "useI18n") ? "bound" : "contained";
}

/**
 * Every literal i18n key the panel renders, sorted. Gap 2's mitigation: the
 * label channel cannot be closed structurally, but it can be PINNED, so that
 * adding a value-bearing key is a visible diff in this gate rather than a
 * silent change inside the panel.
 */
export function renderedLabelKeys(text: string, componentName: string): string[] {
  const source = parse(text, `${componentName}.tsx`);
  const declaration = componentDeclaration(source, componentName);
  if (!declaration?.body) return [];
  const { roots } = producerRoots(declaration, new Set(DEFAULT_PRODUCER_READS));
  const keys = new Set<string>();
  const visit = (node: ts.Node) => {
    if (
      ts.isCallExpression(node) &&
      isLabelCall(node, roots) &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      keys.add(node.arguments[0].text);
    }
    ts.forEachChild(node, visit);
  };
  visit(declaration.body);
  return [...keys].sort();
}

/**
 * The typed-refusal property: an absent value renders a refusal, never a blank,
 * a zero, or an inference.
 *
 * Structural reach and its limit — a contained panel MUST render the sanctioned
 * refusal, and no panel may render a blank in a value slot. Whether a BOUND
 * panel renders the refusal when a producer field is null at runtime is not a
 * property of the source text; that half is behavioural and is carried by C05's
 * rendered-DOM assertions, recorded here rather than left implied.
 */
export function refusalFindings(
  text: string,
  componentName: string,
  producerReads: readonly string[] = DEFAULT_PRODUCER_READS,
): string[] {
  const source = parse(text, `${componentName}.tsx`);
  const declaration = componentDeclaration(source, componentName);
  if (!declaration?.body) return [`panel-missing:${componentName}`];
  const findings = new Set<string>();

  const visit = (node: ts.Node) => {
    if (ts.isJsxExpression(node)) {
      const slot =
        node.parent &&
        ts.isJsxAttribute(node.parent) &&
        ts.isIdentifier(node.parent.name)
          ? `attr:${node.parent.name.text}`
          : "child";
      const expression = node.expression;
      if (!expression) {
        findings.add(`blank-emission:${slot}`);
      } else if (
        expression.kind === ts.SyntaxKind.NullKeyword ||
        (ts.isIdentifier(expression) && expression.text === "undefined") ||
        (ts.isStringLiteral(expression) && expression.text === "") ||
        (ts.isNumericLiteral(expression) && Number(expression.text) === 0)
      ) {
        findings.add(`blank-emission:${slot}`);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(declaration.body);

  if (
    panelEmissionMode(text, componentName, producerReads) === "contained" &&
    !renderedLabelKeys(text, componentName).includes(SANCTIONED_REFUSAL_KEY)
  ) {
    findings.add("refusal-missing");
  }
  return [...findings].sort();
}

// -- gap 1: the cross-file mount graph --------------------------------------

const SOURCE_EXTENSIONS = [".tsx", ".ts", "/index.tsx", "/index.ts"];

type SourceUnit = { file: string; source: ts.SourceFile };

function productionSources(
  root: string,
  overrides: SourceOverrides,
): Array<{ file: string; text: string }> {
  if (!fs.existsSync(root)) return [];
  return fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(root, entry.name);
    if (entry.isDirectory()) return productionSources(file, overrides);
    if (
      !entry.isFile() ||
      ![".ts", ".tsx"].includes(path.extname(file)) ||
      /\.(test|a11y\.test)\.[tj]sx?$/.test(file)
    ) {
      return [];
    }
    return [{ file, text: overrides[file] ?? fs.readFileSync(file, "utf8") }];
  });
}

function resolveImport(
  file: string,
  specifier: string,
  knownFiles: ReadonlySet<string>,
): string | null {
  const root = specifier.startsWith("@/")
    ? path.join(sourceRoot, specifier.slice(2))
    : specifier.startsWith(".")
      ? path.resolve(path.dirname(file), specifier)
      : null;
  if (!root) return null;
  for (const suffix of SOURCE_EXTENSIONS) {
    const candidate = `${root}${suffix}`;
    if (knownFiles.has(candidate) || fs.existsSync(candidate)) return candidate;
  }
  return null;
}

function importTargets(
  file: string,
  source: ts.SourceFile,
  knownFiles: ReadonlySet<string>,
): string[] {
  const targets: string[] = [];
  const visit = (node: ts.Node) => {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      const target = resolveImport(file, node.moduleSpecifier.text, knownFiles);
      if (target) targets.push(target);
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      const target = resolveImport(file, node.arguments[0].text, knownFiles);
      if (target) targets.push(target);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return targets;
}

/** Local computation at a MOUNT site — the same sin, one file over. */
function mountPropFindings(
  initializer: ts.JsxAttributeValue | undefined,
): string[] {
  if (!initializer || !ts.isJsxExpression(initializer)) return [];
  const expression = initializer.expression;
  if (!expression) return ["blank"];
  const findings: string[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isBinaryExpression(node)) {
      if (ARITHMETIC_OPERATORS.has(node.operatorToken.kind)) {
        findings.push("arithmetic");
      }
      if (THRESHOLD_OPERATORS.has(node.operatorToken.kind)) {
        findings.push("threshold");
      }
    }
    if (ts.isConditionalExpression(node)) findings.push("conditional");
    if (ts.isCallExpression(node)) findings.push("call");
    if (ts.isNumericLiteral(node)) findings.push("literal");
    if (ts.isRegularExpressionLiteral(node)) findings.push("regex");
    ts.forEachChild(node, visit);
  };
  visit(expression);
  return [...new Set(findings)].sort();
}

export type MountCensus = {
  findings: string[];
  mounts: Array<{ file: string; name: string; props: number }>;
};

/**
 * Gap 1, carried forward from the ancestor: a value can be minted at the mount
 * site as easily as inside the component.
 *
 * Reachability, not filename, is what excludes the test harness — the harness
 * mounts `PublicSectorReadinessPanel` and is NOT named `*.test.tsx`, so a census
 * that filtered only by filename would count four mounts and be wrong.
 */
export function mountGraphCensus(overrides: SourceOverrides = {}): MountCensus {
  const units = new Map<string, SourceUnit>();
  for (const { file, text } of productionSources(sourceRoot, overrides)) {
    units.set(file, { file, source: parse(text, file) });
  }
  // An override may introduce a file that is not on disk — that is exactly how
  // a smuggled wrapper mount arrives. Without this the census silently walks
  // the real tree and reports the honest count for a dishonest graph.
  for (const [file, text] of Object.entries(overrides)) {
    if (!units.has(file)) units.set(file, { file, source: parse(text, file) });
  }
  const knownFiles = new Set(units.keys());

  const reachable = new Set<string>();
  const queue = [runDetailLayoutPath, governanceTabPath];
  while (queue.length) {
    const file = queue.shift();
    if (!file || reachable.has(file)) continue;
    reachable.add(file);
    const unit = units.get(file);
    if (!unit) continue;
    for (const target of importTargets(file, unit.source, knownFiles)) {
      if (units.has(target)) queue.push(target);
    }
  }

  const findings: string[] = [];
  const mounts: MountCensus["mounts"] = [];
  for (const file of reachable) {
    const unit = units.get(file);
    if (!unit) continue;
    const visit = (node: ts.Node) => {
      if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
        const name = ts.isIdentifier(node.tagName)
          ? node.tagName.text
          : node.tagName.getText();
        if (PANEL_NAMES.has(name)) {
          const relative = path.relative(sourceRoot, file);
          mounts.push({
            file: relative,
            name,
            props: node.attributes.properties.length,
          });
          for (const property of node.attributes.properties) {
            if (ts.isJsxSpreadAttribute(property)) {
              findings.push(`mount-prop-spread:${relative}:${name}`);
              continue;
            }
            if (!ts.isJsxAttribute(property)) continue;
            const propName = ts.isIdentifier(property.name)
              ? property.name.text
              : property.name.getText();
            for (const reason of mountPropFindings(property.initializer)) {
              findings.push(`minted-mount-prop:${relative}:${propName}:${reason}`);
            }
          }
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(unit.source);
  }

  return { findings: [...findings].sort(), mounts };
}
