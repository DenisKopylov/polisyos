import {
  buildBootstrapQueryOptions,
  getWorkspaceNavigation,
  isWorkspaceEnabled,
  resolveWorkspaceKey,
  WORKSPACES,
} from "./workspaces";

describe("workspace registry", () => {
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
    const flags = {
      enableDarkMode: true,
      enableLexKnowledge: false,
      enablePlatformHealth: true,
      enableRunsWorkspace: true,
      enableScenarioComposer: false,
    };

    expect(isWorkspaceEnabled(WORKSPACES.commandCenter, flags)).toBe(true);
    expect(isWorkspaceEnabled(WORKSPACES.lexKnowledge, flags)).toBe(false);
    expect(getWorkspaceNavigation(flags).map((workspace) => workspace.key)).toEqual([
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
    expect(WORKSPACES.runsDecisions.resolveHeader("/runs/run-1/overview")).toEqual({
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
