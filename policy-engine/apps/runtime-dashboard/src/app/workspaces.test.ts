import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

import {
  buildBootstrapQueryOptions,
  getWorkspaceNavigation,
  isWorkspaceEnabled,
  resolveWorkspaceKey,
  WORKSPACES,
} from "./workspaces";
import { buildFeatureFlags } from "@/test/featureFlags";

const workspaceSourcePath = path.join(import.meta.dirname, "workspaces.ts");
const runWorkspacePublicSurface = "@/features/runs/workspaces.public";

function dependencySpecifiers(file: string, text: string): string[] {
  const source = ts.createSourceFile(
    file,
    text,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const specifiers: string[] = [];
  const visit = (node: ts.Node) => {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      specifiers.push(node.moduleSpecifier.text);
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      specifiers.push(node.arguments[0].text);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return specifiers;
}

function runFeatureSpecifiers(file: string, text: string): string[] {
  return dependencySpecifiers(file, text).filter(
    (specifier) =>
      specifier === "@/features/runs" ||
      specifier.startsWith("@/features/runs/"),
  );
}

function runFeatureBoundaryViolations(file: string, text: string): string[] {
  return runFeatureSpecifiers(file, text).filter(
    (specifier) => specifier !== runWorkspacePublicSurface,
  );
}

describe("workspace registry", () => {
  it("imports run workspace data only through the feature public surface", () => {
    const source = fs.readFileSync(workspaceSourcePath, "utf8");
    expect(runFeatureSpecifiers(workspaceSourcePath, source)).toEqual([
      runWorkspacePublicSurface,
    ]);
    expect(runFeatureBoundaryViolations(workspaceSourcePath, source)).toEqual(
      [],
    );

    const probePath = path.join(import.meta.dirname, "CorruptedWorkspace.ts");
    const corruptions = [
      'import { runsSampleQueryOptions } from "@/features/runs";',
      'import { runsSampleQueryOptions } from "@/features/runs/api/useRunsSample";',
      'export { runsSampleQueryOptions } from "@/features/runs/api/useRunsSample";',
      'const runs = import("@/features/runs/api/useRunsSample");',
      'import * as RunsApi from "@/features/runs/api/useRunsSample";',
    ];
    expect(
      corruptions.flatMap((text) =>
        runFeatureBoundaryViolations(probePath, text),
      ),
    ).toEqual([
      "@/features/runs",
      "@/features/runs/api/useRunsSample",
      "@/features/runs/api/useRunsSample",
      "@/features/runs/api/useRunsSample",
      "@/features/runs/api/useRunsSample",
    ]);
  });

  it("resolves canonical and alias paths", () => {
    expect(resolveWorkspaceKey("/")).toBe("commandCenter");
    expect(resolveWorkspaceKey("/compose")).toBe("scenarioComposer");
    expect(resolveWorkspaceKey("/launch")).toBe("scenarioComposer");
    expect(resolveWorkspaceKey("/runs/compare")).toBe("runsDecisions");
    expect(resolveWorkspaceKey("/artifacts/art-1")).toBe("runsDecisions");
    expect(resolveWorkspaceKey("/sources")).toBe("evidenceFabric");
    expect(resolveWorkspaceKey("/data")).toBe("evidenceFabric");
    expect(resolveWorkspaceKey("/lex")).toBe("lexKnowledge");
    expect(resolveWorkspaceKey("/health")).toBe("platformHealth");
  });

  it("keeps workspace metadata decision-complete", () => {
    expect(buildBootstrapQueryOptions("capabilities").queryKey).toEqual([
      "control",
      "capabilities",
    ]);
    expect(buildBootstrapQueryOptions("runsSample").queryKey).toEqual([
      "runtime",
      "runs",
      {
        limit: 24,
      },
    ]);
  });

  it("builds bootstrap query options for every registered bootstrap key", () => {
    const keys = [
      "capabilities",
      "connectors",
      "dataIndexStats",
      "dataPromotionCandidates",
      "health",
      "llmProfiles",
      "runs",
      "runsSample",
      "sourceProfiles",
    ] as const;
    const buildByKey = {
      capabilities: () => buildBootstrapQueryOptions("capabilities"),
      connectors: () => buildBootstrapQueryOptions("connectors"),
      dataIndexStats: () => buildBootstrapQueryOptions("dataIndexStats"),
      dataPromotionCandidates: () =>
        buildBootstrapQueryOptions("dataPromotionCandidates"),
      health: () => buildBootstrapQueryOptions("health"),
      llmProfiles: () => buildBootstrapQueryOptions("llmProfiles"),
      runs: () => buildBootstrapQueryOptions("runs"),
      runsSample: () => buildBootstrapQueryOptions("runsSample"),
      sourceProfiles: () => buildBootstrapQueryOptions("sourceProfiles"),
    } as const;

    for (const key of keys) {
      const options = buildByKey[key]();
      expect(options.queryKey).toBeDefined();
      expect(options.queryFn).toBeDefined();
    }
  });

  it("filters navigation by feature flags and keeps flagless workspaces enabled", () => {
    const flags = buildFeatureFlags({
      enableClerkMode: true,
      enableLexKnowledge: false,
      enableScenarioComposer: false,
    });

    expect(isWorkspaceEnabled(WORKSPACES.commandCenter, flags)).toBe(true);
    expect(isWorkspaceEnabled(WORKSPACES.lexKnowledge, flags)).toBe(false);
    expect(
      getWorkspaceNavigation(flags).map((workspace) => workspace.key),
    ).toEqual([
      "commandCenter",
      "runsDecisions",
      "evidenceFabric",
      "platformHealth",
    ]);
  });

  it("resolves workspace headers for list and detail routes", () => {
    expect(WORKSPACES.commandCenter.resolveHeader("/")).toEqual({
      eyebrowKey: "shell.routes.commandCenterEyebrow",
      subtitleKey: "pages.dashboard.subtitle",
      titleKey: "shell.routes.commandCenterTitle",
    });
    expect(WORKSPACES.runsDecisions.resolveHeader("/runs")).toEqual({
      eyebrowKey: "pages.runs.title",
      subtitleKey: "pages.runs.subtitle",
      titleKey: "pages.runs.explorerTitle",
    });
    expect(
      WORKSPACES.runsDecisions.resolveHeader("/runs/run-1/overview"),
    ).toEqual({
      eyebrowKey: "shell.routes.runAnalysisEyebrow",
      subtitleKey: "pages.runs.subtitle",
      titleKey: "shell.routes.runAnalysisTitle",
    });
    expect(WORKSPACES.platformHealth.resolveHeader("/platform")).toEqual({
      eyebrowKey: "shell.header.runtime",
      subtitleKey: "shell.subtitle",
      titleKey: "shell.routes.platformTitle",
    });
  });
});
