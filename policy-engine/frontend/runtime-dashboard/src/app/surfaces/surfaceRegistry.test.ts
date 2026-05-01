import {
  getChildSurfaces,
  getCommandPaletteSurfaceEntries,
  getNestedSurfacesForWorkspace,
  getSurfaceById,
  RUN_DETAIL_SURFACES,
  SURFACE_REGISTRY,
} from "./surfaceRegistry";

describe("surface registry", () => {
  it("keeps run tabs in the registry and outside top-level sidebar placement", () => {
    expect(RUN_DETAIL_SURFACES.map((surface) => surface.id)).toEqual([
      "runs.overview",
      "runs.causal",
      "runs.governance",
      "runs.evidence",
      "runs.workflow",
      "runs.artifacts",
      "runs.agents",
      "runs.debug",
    ]);
    expect(
      RUN_DETAIL_SURFACES.every(
        (surface) => surface.placement === "workspace-tab",
      ),
    ).toBe(true);
  });

  it("resolves nested panels under parent surfaces", () => {
    expect(getSurfaceById("runs.causalAtlas")?.parentId).toBe("runs.causal");
    expect(
      getChildSurfaces("runs.causal").map((surface) => surface.id),
    ).toEqual(["runs.causalAtlas", "runs.identifiabilitySurface"]);
    expect(
      getChildSurfaces("runs.overview").map((surface) => surface.id),
    ).toEqual([
      "runs.sensitivityRotor",
      "runs.cohortTimeTraveler",
      "runs.stakeholderLens",
      "runs.argumentMap",
      "runs.comprehensionLayer",
      "runs.glossaryLens",
      "runs.confidenceLadder",
      "runs.thresholdContract",
      "runs.globalTrustDial",
      "runs.annotationSurface",
      "runs.readingOnboarding",
    ]);
    expect(
      getChildSurfaces("runs.artifacts").map((surface) => surface.id),
    ).toEqual([
      "runs.modelCard",
      "runs.publicViewer",
      "runs.evidenceWallet",
      "runs.bureaucraticForms",
    ]);
    expect(
      getChildSurfaces("runs.evidence").map((surface) => surface.id),
    ).toEqual(["runs.embargoOverlay", "runs.coverageMap"]);
    expect(
      getChildSurfaces("runs.governance").map((surface) => surface.id),
    ).toEqual([
      "runs.stressTestTheatre",
      "runs.disputeRegistry",
      "runs.fairnessAudit",
      "runs.harmSurface",
      "runs.slowReviewMode",
      "runs.revocationLedger",
    ]);
    expect(
      getNestedSurfacesForWorkspace("runsDecisions").some(
        (surface) => surface.id === "runs.runChoreography",
      ),
    ).toBe(true);
  });

  it("adds contextual run surfaces to the command palette only when a run is active", () => {
    const withoutRun = getCommandPaletteSurfaceEntries();
    expect(withoutRun.some((surface) => surface.id === "runs.causal")).toBe(
      false,
    );

    const withRun = getCommandPaletteSurfaceEntries({
      runId: "run-42",
    });
    expect(withRun.find((surface) => surface.id === "runs.causal")?.href).toBe(
      "/runs/run-42/causal",
    );
    expect(
      withRun.find((surface) => surface.id === "runs.runChoreography")?.href,
    ).toBe("/runs/run-42/workflow?surface=choreography");
    expect(
      withRun.find((surface) => surface.id === "fabric.freshnessBraid")?.href,
    ).toBe("/evidence?runId=run-42&surface=freshness-braid");
    expect(
      withRun.find((surface) => surface.id === "fabric.connectorCards")?.href,
    ).toBe("/evidence?runId=run-42&surface=connector-cards");
    expect(
      withRun.find((surface) => surface.id === "runs.identifiabilitySurface")
        ?.href,
    ).toBe("/runs/run-42/overview?surface=identifiability-surface");
    expect(
      withRun.find((surface) => surface.id === "runs.sensitivityRotor")?.href,
    ).toBe("/runs/run-42/overview?surface=sensitivity-rotor");
    expect(
      withRun.find((surface) => surface.id === "runs.cohortTimeTraveler")?.href,
    ).toBe("/runs/run-42/overview?surface=cohort-time-traveler");
    expect(
      withRun.find((surface) => surface.id === "runs.stressTestTheatre")?.href,
    ).toBe("/runs/run-42/overview?surface=stress-test-theatre");
    expect(
      withRun.find((surface) => surface.id === "runs.stakeholderLens")?.href,
    ).toBe("/runs/run-42/overview?surface=stakeholder-lens");
    expect(
      withRun.find((surface) => surface.id === "runs.fairnessAudit")?.href,
    ).toBe("/runs/run-42/governance?surface=fairness-audit");
    expect(
      withRun.find((surface) => surface.id === "runs.harmSurface")?.href,
    ).toBe("/runs/run-42/governance?surface=harm-surface");
    expect(
      withRun.find((surface) => surface.id === "runs.embargoOverlay")?.href,
    ).toBe("/runs/run-42/overview?surface=embargo-overlay");
    expect(
      withRun.find((surface) => surface.id === "runs.slowReviewMode")?.href,
    ).toBe("/runs/run-42/governance?surface=slow-review");
    expect(
      withRun.find((surface) => surface.id === "runs.revocationLedger")?.href,
    ).toBe("/runs/run-42/governance?surface=revocation-ledger");
    expect(
      withRun.find((surface) => surface.id === "runs.argumentMap")?.href,
    ).toBe("/runs/run-42/overview?surface=argument-map");
    expect(
      withRun.find((surface) => surface.id === "runs.comprehensionLayer")?.href,
    ).toBe("/runs/run-42/overview?surface=comprehension-layer");
    expect(
      withRun.find((surface) => surface.id === "runs.glossaryLens")?.href,
    ).toBe("/runs/run-42/overview?surface=glossary-lens");
    expect(
      withRun.find((surface) => surface.id === "runs.confidenceLadder")?.href,
    ).toBe("/runs/run-42/overview?surface=confidence-ladder");
    expect(
      withRun.find((surface) => surface.id === "runs.modelCard")?.href,
    ).toBe("/runs/run-42/overview?surface=model-card");
    expect(
      withRun.find((surface) => surface.id === "runs.publicViewer")?.href,
    ).toBe("/runs/run-42/overview?surface=public-viewer");
    expect(
      withRun.find((surface) => surface.id === "runs.coverageMap")?.href,
    ).toBe("/runs/run-42/overview?surface=coverage-map");
    expect(
      withRun.find((surface) => surface.id === "runs.thresholdContract")?.href,
    ).toBe("/runs/run-42/overview?surface=threshold-contract");
    expect(
      withRun.find((surface) => surface.id === "runs.globalTrustDial")?.href,
    ).toBe("/runs/run-42/overview?surface=global-trust-dial");
    expect(
      withRun.find((surface) => surface.id === "runs.annotationSurface")?.href,
    ).toBe("/runs/run-42/overview?surface=annotation-surface");
    expect(
      withRun.find((surface) => surface.id === "runs.evidenceWallet")?.href,
    ).toBe("/runs/run-42/overview?surface=evidence-wallet");
    expect(
      withRun.find((surface) => surface.id === "runs.readingOnboarding")?.href,
    ).toBe("/runs/run-42/overview?surface=reading-onboarding");
    expect(
      withRun.find((surface) => surface.id === "runs.bureaucraticForms")?.href,
    ).toBe("/runs/run-42/overview?surface=bureaucratic-forms");
  });

  it("filters command surfaces through workspace, capability, and permission gates", () => {
    const surfaces = getCommandPaletteSurfaceEntries({
      canAccessPermission: (permission) => permission !== "runs.review",
      hasCapability: (capability) => capability !== "evaluator_reports",
      isWorkspaceAllowed: (workspaceKey) => workspaceKey !== "lexKnowledge",
      runId: "run-42",
    });

    expect(surfaces.some((surface) => surface.id === "runs.causal")).toBe(true);
    expect(surfaces.some((surface) => surface.id === "runs.governance")).toBe(
      false,
    );
    expect(
      surfaces.some((surface) => surface.id === "runs.disputeRegistry"),
    ).toBe(false);
    expect(
      surfaces.some((surface) => surface.id === "runs.stressTestTheatre"),
    ).toBe(false);
    expect(
      surfaces.some((surface) => surface.id === "runs.fairnessAudit"),
    ).toBe(false);
    expect(surfaces.some((surface) => surface.id === "runs.harmSurface")).toBe(
      false,
    );
    expect(
      surfaces.some((surface) => surface.id === "runs.slowReviewMode"),
    ).toBe(false);
    expect(
      surfaces.some((surface) => surface.id === "runs.revocationLedger"),
    ).toBe(false);
    expect(
      surfaces.some((surface) => surface.id === "runs.annotationSurface"),
    ).toBe(false);
    expect(
      surfaces.some((surface) => surface.id === "runs.evidenceWallet"),
    ).toBe(false);
    expect(
      surfaces.some((surface) => surface.id === "runs.readingOnboarding"),
    ).toBe(false);
    expect(surfaces.some((surface) => surface.id === "runs.coverageMap")).toBe(
      true,
    );
    expect(
      surfaces.some((surface) => surface.id === "workspace.lexKnowledge"),
    ).toBe(false);
  });

  it("keeps surface identifiers unique", () => {
    const ids = SURFACE_REGISTRY.map((surface) => surface.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("keeps parent links and semantic ids structurally valid", () => {
    const ids = new Set(SURFACE_REGISTRY.map((surface) => surface.id));
    const semanticIds = SURFACE_REGISTRY.map(
      (surface) => surface.semanticExplanationId,
    );
    const panelsWithoutParent: string[] = [];
    const surfacesWithMissingParent: string[] = [];

    for (const surface of SURFACE_REGISTRY) {
      expect(surface.labelKey).toBeTruthy();
      expect(surface.descriptionKey).toBeTruthy();
      if (surface.placement === "panel") {
        if (!surface.parentId) {
          panelsWithoutParent.push(surface.id);
        }
      }
      if (surface.parentId) {
        if (!ids.has(surface.parentId)) {
          surfacesWithMissingParent.push(surface.id);
        }
      }
    }

    expect(panelsWithoutParent).toEqual([]);
    expect(surfacesWithMissingParent).toEqual([]);
    expect(new Set(semanticIds).size).toBe(semanticIds.length);
  });
});
