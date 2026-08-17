import fs from "node:fs";
import path from "node:path";
import ts from "typescript";
import { describe, expect, it } from "vitest";

/**
 * DS16-C01 negative 4 (`P05`/`P15`, with `P29` and `P38`) — the successor
 * authority negative: a panel that emits a value the producer did not supply
 * fails, BY CONSTRUCTION and not by inspection.
 *
 * Its ancestor, `readinessScientificContainment.test.ts`, proves CONSTANT
 * emission: `expressions === 0`, `components === 0`, `calls === 0`, zero
 * parameters, zero mount props. `DS4-C23` proved "this panel cannot emit
 * anything". DS16 must prove "this panel cannot emit anything it did not
 * receive", which is strictly harder in the direction that matters and
 * strictly weaker in the direction that DS16 exists to open.
 *
 * NAMED DIVERGENCE FROM THE ANCESTOR (`P38` — say where property and
 * implementation part company, do not assume they coincide):
 *
 *  (a) The successor PERMITS `{composition.readinessScore}` — a value read
 *      straight off a sanctioned producer. The ancestor REJECTS it, because
 *      `expressions === 0` admits nothing but the constant. This divergence is
 *      the entire reason C02 exists; a successor that did not diverge here
 *      would just be the ancestor.
 *  (b) The successor PERMITS a label under a different i18n key. The ancestor
 *      pins the exact key `common.unavailable`, which it can do only while the
 *      panel is constant. A bound panel needs labels, and a label is not a
 *      value. The gate guards the VALUE path.
 *
 * Therefore the successor is NOT a strict superset of the ancestor, and it
 * cannot be: the ancestor's catch-set contains the very producer bindings this
 * slice exists to permit. The honest formulation, verified below, is that the
 * successor catches every ancestor corruption THAT MINTS A VALUE, and adds the
 * case no structural constant-emission gate can see — local computation
 * arriving through an otherwise entirely legitimate producer field.
 *
 * NOT CARRIED HERE: the ancestor's cross-file mount census (reachability, mount
 * counts, zero mount props). That is a mount-graph property, not a value-minting
 * property, and C02 carries it forward unchanged; this analyzer is single-source
 * by design and case 11 below is recorded as out of scope rather than silently
 * dropped.
 */

const dashboardRoot = path.resolve(import.meta.dirname, "../../../..");
const sourceRoot = path.join(dashboardRoot, "src");
const readinessPanel = path.join(
  sourceRoot,
  "features/runs/components/PublicSectorReadinessPanel.tsx",
);
const scientificPanel = path.join(
  sourceRoot,
  "features/runs/components/ScientificDepthPanel.tsx",
);

/**
 * The sanctioned producer surface. Today it holds only the i18n binding,
 * because the readiness/scientific-depth producer DOES NOT EXIST — zero files
 * in `src/` or `schemas/` match `public_sector_readiness|scientific_depth|
 * readiness_composition`. C02/C03 extend this set when they build the producer,
 * and extending it is a deliberate, reviewable act rather than a side effect.
 */
const DEFAULT_PRODUCER_READS = ["useI18n"] as const;

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

/** Unaliased named imports — an alias is how the ancestor's case 2 escapes. */
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

/** Walk a member chain down to the identifier it is ultimately read from. */
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

/**
 * Every finding this gate can report. A value the producer did not supply
 * reaches the glass through exactly one of these, and each is reproduced RED
 * below.
 */
export function mintedValueFindings(
  text: string,
  componentName: string,
  producerReads: readonly string[] = DEFAULT_PRODUCER_READS,
): string[] {
  const source = parse(text, `${componentName}.tsx`);
  const declaration = source.statements.find(
    (statement): statement is ts.FunctionDeclaration =>
      ts.isFunctionDeclaration(statement) && statement.name?.text === componentName,
  );
  if (!declaration?.body) return [`panel-missing:${componentName}`];

  const sanctioned = new Set(producerReads);
  const imported = unaliasedImports(source);
  const declared = localComponentNames(source);
  const findings = new Set<string>();
  const sanctionedCalls = new Set<ts.Node>();
  const roots = new Set<string>();

  // Parameters are producer input: a panel may be handed its values as props.
  for (const parameter of declaration.parameters) {
    if (ts.isIdentifier(parameter.name)) roots.add(parameter.name.text);
    if (ts.isObjectBindingPattern(parameter.name)) {
      for (const element of parameter.name.elements) {
        if (ts.isIdentifier(element.name)) roots.add(element.name.text);
      }
    }
  }

  // Producer reads: `const { x } = useSanctionedProducer();`
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
      if (initializer.arguments.some((argument) => !ts.isStringLiteral(argument))) {
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
        node.parent && ts.isJsxAttribute(node.parent) && ts.isIdentifier(node.parent.name)
          ? `attr:${node.parent.name.text}`
          : "child";
      classifyRendered(node.expression, slot);
    }
    ts.forEachChild(node, visit);
  };
  visit(declaration.body);

  if (returns > 1) findings.add("local-control-flow");

  // Anything still calling at this point is neither a producer read nor a label.
  const sweep = (node: ts.Node) => {
    if (ts.isCallExpression(node) && !sanctionedCalls.has(node)) {
      findings.add(`unbound-call:${calleeName(node)}`);
    }
    ts.forEachChild(node, sweep);
  };
  sweep(declaration.body);

  return [...findings].sort();
}

const readinessSource = fs.readFileSync(readinessPanel, "utf8");
const scientificSource = fs.readFileSync(scientificPanel, "utf8");

/** The shape C02 is expected to land: a producer read, rendered untouched. */
const BOUND_PRODUCER_PANEL = `import { useI18n } from "@/shared/i18n/LocaleProvider";
import { useReadinessComposition } from "@/features/runs/producers/useReadinessComposition";

export function PublicSectorReadinessPanel() {
  const { t } = useI18n();
  const { composition } = useReadinessComposition();

  return (
    <section data-testid="public-sector-readiness-panel">
      {composition.readinessScore}
      {composition.refusal}
      {t("readiness.caption")}
    </section>
  );
}
`;

/**
 * THE CRUX. Identical imports, identical sanctioned producer read, identical
 * legitimate fields — and a weighted composite computed on the glass. This is
 * exactly the `DS4-C23` sin (readiness composed from local thresholds and dwell
 * state) surviving inside an otherwise blameless producer binding, and it is
 * the case a constant-emission gate cannot distinguish from the compliant panel
 * once `expressions === 0` is relaxed to let producer values through.
 */
const COMPUTING_PRODUCER_PANEL = `import { useI18n } from "@/shared/i18n/LocaleProvider";
import { useReadinessComposition } from "@/features/runs/producers/useReadinessComposition";

export function PublicSectorReadinessPanel() {
  const { t } = useI18n();
  const { composition } = useReadinessComposition();

  return (
    <section data-testid="public-sector-readiness-panel">
      {composition.coverage * 0.6 + composition.dwell * 0.4}
      {t("readiness.caption")}
    </section>
  );
}
`;

/** The same minting through a threshold rather than arithmetic. */
const THRESHOLD_PRODUCER_PANEL = `import { useI18n } from "@/shared/i18n/LocaleProvider";
import { useReadinessComposition } from "@/features/runs/producers/useReadinessComposition";

export function PublicSectorReadinessPanel() {
  const { t } = useI18n();
  const { composition } = useReadinessComposition();

  return (
    <section data-testid="public-sector-readiness-panel">
      {composition.coverage >= composition.floor ? t("ready") : t("blocked")}
    </section>
  );
}
`;

const BOUND_PRODUCER_READS = ["useI18n", "useReadinessComposition"] as const;

describe("DS16-C01 negative 4 — successor authority", () => {
  it("holds on both panels as they stand, and reports the property it proves", () => {
    expect(mintedValueFindings(readinessSource, "PublicSectorReadinessPanel")).toEqual(
      [],
    );
    expect(mintedValueFindings(scientificSource, "ScientificDepthPanel")).toEqual([]);
  });

  it("catches a locally computed value arriving through a legitimate producer field", () => {
    // The compliant bound panel is green ONLY once its producer read is
    // sanctioned — proving the gate is not simply passing everything.
    expect(
      mintedValueFindings(
        BOUND_PRODUCER_PANEL,
        "PublicSectorReadinessPanel",
        BOUND_PRODUCER_READS,
      ),
    ).toEqual([]);

    // Same producer, same sanction, same legitimate fields — and the composite
    // is caught. This is the negative C02's successor gate must satisfy.
    expect(
      mintedValueFindings(
        COMPUTING_PRODUCER_PANEL,
        "PublicSectorReadinessPanel",
        BOUND_PRODUCER_READS,
      ),
    ).toEqual(["local-arithmetic", "untraceable-render:child"]);

    expect(
      mintedValueFindings(
        THRESHOLD_PRODUCER_PANEL,
        "PublicSectorReadinessPanel",
        BOUND_PRODUCER_READS,
      ),
      // The branch labels are swept too: a call inside a rejected conditional
      // is never reached by the label sanction, so it stays accounted for.
    ).toEqual(["local-conditional:child", "local-threshold", "unbound-call:t"]);
  });

  it("keeps the unsanctioned producer read closed", () => {
    // Without the sanction, the very same compliant panel is refused: a panel
    // may not reach for an arbitrary hook and call the result a producer.
    expect(
      mintedValueFindings(BOUND_PRODUCER_PANEL, "PublicSectorReadinessPanel"),
    ).toEqual(["unsanctioned-producer-read:useReadinessComposition"]);
  });

  it("catches every ancestor corruption that mints a value", () => {
    const cases: Array<[string, string, string, readonly string[]]> = [
      [
        "direct-helper",
        readinessSource.replace(
          "const { t } = useI18n();",
          "const { t } = useI18n();\n  const value = helper();",
        ),
        "PublicSectorReadinessPanel",
        ["unsanctioned-producer-read:helper"],
      ],
      [
        "aliased-i18n-import",
        scientificSource.replace("{ useI18n }", "{ useI18n as i18n }"),
        "ScientificDepthPanel",
        ["unimported-producer-read:useI18n"],
      ],
      [
        "component-child",
        scientificSource.replace('{t("common.unavailable")}', "<Unavailable />"),
        "ScientificDepthPanel",
        ["opaque-component-child:Unavailable"],
      ],
      [
        "literal-text",
        scientificSource.replace(
          '{t("common.unavailable")}',
          '{t("common.unavailable")} approved',
        ),
        "ScientificDepthPanel",
        ["literal-text-rendered"],
      ],
      [
        "renamed-binding",
        scientificSource.replace(
          "const { t } = useI18n();",
          "const { arbitrary: t } = useI18n();",
        ),
        "ScientificDepthPanel",
        ["renamed-producer-binding"],
      ],
      [
        "control-flow",
        scientificSource.replace(
          "  return (",
          "  if (window.name) return null;\n\n  return (",
        ),
        "ScientificDepthPanel",
        ["local-control-flow"],
      ],
      [
        "off-jsx-call",
        scientificSource.replace(
          "const { t } = useI18n();",
          'const { t } = useI18n();\n  t("common.unavailable");',
        ),
        "ScientificDepthPanel",
        ["unbound-call:t"],
      ],
      [
        "prop-spread",
        readinessSource.replace("<section", "<section {...props}"),
        "PublicSectorReadinessPanel",
        ["prop-spread"],
      ],
      [
        "conditional-render",
        scientificSource.replace(
          '{t("common.unavailable")}',
          '{ready ? t("common.unavailable") : "waiting"}',
        ),
        "ScientificDepthPanel",
        ["local-conditional:child", "unbound-call:t"],
      ],
    ];

    for (const [name, corrupted, component, expected] of cases) {
      const findings = mintedValueFindings(corrupted, component);
      expect(findings, `${name} must be caught`).not.toEqual([]);
      expect(findings, `${name} findings`).toEqual(expected);
    }
  });

  it("names the two cases where it diverges from the ancestor rather than hiding them", () => {
    // (a) A producer value is PERMITTED here and forbidden by the ancestor.
    expect(
      mintedValueFindings(
        BOUND_PRODUCER_PANEL,
        "PublicSectorReadinessPanel",
        BOUND_PRODUCER_READS,
      ),
    ).toEqual([]);

    // (b) A different i18n key is a label change, not a minted value. The
    // ancestor rejects it because it pins the constant; the successor does not.
    expect(
      mintedValueFindings(
        scientificSource.replace("common.unavailable", "common.unknown"),
        "ScientificDepthPanel",
      ),
    ).toEqual([]);
  });

  it("fails when the property is removed but the markers remain (P29)", () => {
    // The `P29` probe: keep every marker the compliant panel carries — the
    // sanctioned import, the sanctioned binding, the section, the testid, the
    // i18n label — and remove only the property, by minting the value inline.
    const markersIntact = readinessSource.replace(
      '{t("common.unavailable")}',
      '{t("common.unavailable")}\n      {0.87}',
    );

    expect(markersIntact).toContain('import { useI18n } from "@/shared/i18n/LocaleProvider";');
    expect(markersIntact).toContain("const { t } = useI18n();");
    expect(markersIntact).toContain('data-testid="public-sector-readiness-panel"');
    expect(markersIntact).toContain('{t("common.unavailable")}');

    expect(
      mintedValueFindings(markersIntact, "PublicSectorReadinessPanel"),
    ).toEqual(["literal-value-rendered:child"]);
  });
});
