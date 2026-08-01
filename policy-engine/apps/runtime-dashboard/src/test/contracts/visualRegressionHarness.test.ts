import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

import playwrightConfig from "../../../playwright.config";

const dashboardRoot = path.resolve(import.meta.dirname, "../../..");
const visualSpecPath = path.join(
  dashboardRoot,
  "e2e/runtime-dashboard.visual.spec.ts",
);
const snapshotRoot = `${visualSpecPath}-snapshots`;

function sourceFile(text: string) {
  return ts.createSourceFile(
    visualSpecPath,
    text,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
}

function isVisualTestCall(node: ts.Node): node is ts.CallExpression {
  return (
    ts.isCallExpression(node) &&
    ts.isIdentifier(node.expression) &&
    node.expression.text === "test" &&
    node.arguments.length >= 2
  );
}

function enclosingTestCallback(
  node: ts.Node,
): ts.ArrowFunction | ts.FunctionExpression | null {
  let current: ts.Node | undefined = node.parent;
  while (current) {
    if (ts.isArrowFunction(current) || ts.isFunctionExpression(current)) {
      const parent: ts.Node = current.parent;
      if (isVisualTestCall(parent) && parent.arguments[1] === current) {
        return current;
      }
    }
    current = current.parent;
  }
  return null;
}

function isDirectTestStatement(
  call: ts.CallExpression,
  callback: ts.ArrowFunction | ts.FunctionExpression,
) {
  if (!ts.isBlock(callback.body)) {
    return false;
  }
  let current: ts.Node = call;
  while (current.parent && current.parent !== callback.body) {
    current = current.parent;
  }
  return current.parent === callback.body && ts.isExpressionStatement(current);
}

function analyzeSnapshotCalls(text: string) {
  const references: string[] = [];
  const violations: string[] = [];
  const visit = (node: ts.Node) => {
    if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.name.text === "toHaveScreenshot"
    ) {
      const callback = enclosingTestCallback(node);
      if (!callback || !isDirectTestStatement(node, callback)) {
        violations.push(
          "screenshot call must be a direct visual-test statement",
        );
      }
      if (!ts.isStringLiteral(node.arguments[0])) {
        violations.push("screenshot name must be a literal");
      } else {
        references.push(node.arguments[0].text);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile(text));
  return {
    references: references.sort(),
    violations: violations.sort(),
  };
}

function committedSnapshotRefs(files: readonly string[]) {
  return files
    .filter((file) => file.endsWith(".png"))
    .map((file) => {
      const match = /^(.+)-chromium-[^.]+\.png$/.exec(file);
      if (!match) {
        throw new TypeError(`unexpected visual snapshot filename: ${file}`);
      }
      return `${match[1]}.png`;
    })
    .sort();
}

function fixtureServerCommand() {
  const servers = Array.isArray(playwrightConfig.webServer)
    ? playwrightConfig.webServer
    : playwrightConfig.webServer
      ? [playwrightConfig.webServer]
      : [];
  const server = servers.find((candidate) =>
    String(candidate.url).includes("127.0.0.1:8000"),
  );
  return server?.command ?? "";
}

function fixtureInvocationDeclaresTestExtra(command: string) {
  const argv = command.trim().split(/\s+/);
  if (argv[0] !== "uv" || argv[1] !== "run") {
    return false;
  }
  const pythonIndex = argv.indexOf("python");
  if (
    pythonIndex < 0 ||
    argv[pythonIndex + 1] !==
      "apps/runtime-dashboard/scripts/serve_fixture_runtime_api.py"
  ) {
    return false;
  }
  const uvArguments = argv.slice(2, pythonIndex);
  return uvArguments.some(
    (argument, index) =>
      argument === "--extra=test" ||
      (argument === "--extra" && uvArguments[index + 1] === "test"),
  );
}

describe("visual regression harness", () => {
  it("keeps executable screenshot references and committed snapshots one-to-one", () => {
    const spec = fs.readFileSync(visualSpecPath, "utf8");
    const analysis = analyzeSnapshotCalls(spec);
    const snapshotFiles = fs.readdirSync(snapshotRoot);
    const committed = committedSnapshotRefs(snapshotFiles);

    expect(analysis.violations).toEqual([]);
    expect(new Set(analysis.references).size).toBe(analysis.references.length);
    expect(committed).toEqual(analysis.references);

    expect(
      committedSnapshotRefs([...snapshotFiles, "orphan-chromium-darwin.png"]),
    ).not.toEqual(analysis.references);
    expect(committedSnapshotRefs(snapshotFiles.slice(1))).not.toEqual(
      analysis.references,
    );

    const firstReference = analysis.references[0];
    expect(firstReference).toBeDefined();
    const dynamicName = spec.replace(
      JSON.stringify(firstReference),
      "dynamicSnapshotName",
    );
    expect(analyzeSnapshotCalls(dynamicName).violations).toContain(
      "screenshot name must be a literal",
    );
    expect(
      analyzeSnapshotCalls(
        `${spec}\nvoid expect(null).toHaveScreenshot("dead.png");`,
      ).violations,
    ).toContain("screenshot call must be a direct visual-test statement");
  });

  it("declares the fixture server test dependency", () => {
    const command = fixtureServerCommand();
    const stripped = command.replace(/--extra(?:=|\s+)test/, "");

    expect(fixtureInvocationDeclaresTestExtra(command)).toBe(true);
    expect(fixtureInvocationDeclaresTestExtra(stripped)).toBe(false);
    expect(
      fixtureInvocationDeclaresTestExtra(`echo --extra test && ${stripped}`),
    ).toBe(false);
  });
});
