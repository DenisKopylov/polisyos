import { describe, expect, it } from "vitest";

import {
  classifyOpaqueBackgroundContrast,
  hasOpaqueBackground,
  OPAQUE_BACKGROUND_CONTRAST_SOURCES,
  type OpaqueBackgroundContrastObservation,
} from "./opaqueBackgroundContrast";

const EXPECTED_SOURCES = [
  {
    sourceId: "badge-neutral",
    ownerCluster: "C01",
    component: "Badge",
    selector: '[data-opaque-contrast-source="badge-neutral"]',
  },
  {
    sourceId: "provenance-popover",
    ownerCluster: "C06",
    component: "ProvenancePopover",
    selector: '[data-opaque-contrast-source="provenance-popover"]',
  },
  {
    sourceId: "provenance-mini-graph",
    ownerCluster: "C06",
    component: "ProvenanceMiniGraph",
    selector: '[data-opaque-contrast-source="provenance-mini-graph"]',
  },
  {
    sourceId: "time-semantics-label",
    ownerCluster: "C09",
    component: "TimeSemanticsLabel",
    selector: '[data-opaque-contrast-source="time-semantics-label"]',
  },
  {
    sourceId: "candidate-frame",
    ownerCluster: "C14",
    component: "CandidateFrame",
    selector: '[data-opaque-contrast-source="candidate-frame"]',
  },
  {
    sourceId: "negative-certificate-card",
    ownerCluster: "C14",
    component: "NegativeCertificateCard",
    selector: '[data-opaque-contrast-source="negative-certificate-card"]',
  },
  {
    sourceId: "weakest-link-explainer",
    ownerCluster: "C14",
    component: "WeakestLinkExplainer",
    selector: '[data-opaque-contrast-source="weakest-link-explainer"]',
  },
] as const;

const EXPECTED_CLUSTER_COUNTS = {
  C01: 1,
  C06: 2,
  C09: 1,
  C14: 3,
} as const;

function passingObservations(): OpaqueBackgroundContrastObservation[] {
  return OPAQUE_BACKGROUND_CONTRAST_SOURCES.map(({ sourceId }) => ({
    sourceId,
    opaqueBackdrop: true,
    violationCount: 0,
    incompleteCount: 0,
    contrastPasses: [{ contrastRatio: 7.2, expectedContrastRatio: 4.5 }],
  }));
}

function replaceObservation(
  sourceId: string,
  replacement: Partial<OpaqueBackgroundContrastObservation>,
): OpaqueBackgroundContrastObservation[] {
  return passingObservations().map((observation) =>
    observation.sourceId === sourceId
      ? { ...observation, ...replacement }
      : observation,
  );
}

describe("opaque background contrast evidence", () => {
  it("freezes the four-cluster, seven-source denominator", () => {
    const sourceIds = OPAQUE_BACKGROUND_CONTRAST_SOURCES.map(
      ({ sourceId }) => sourceId,
    );
    const clusterCounts = Object.fromEntries(
      Object.keys(EXPECTED_CLUSTER_COUNTS).map((cluster) => [
        cluster,
        OPAQUE_BACKGROUND_CONTRAST_SOURCES.filter(
          ({ ownerCluster }) => ownerCluster === cluster,
        ).length,
      ]),
    );

    expect(sourceIds).toHaveLength(7);
    expect(new Set(sourceIds).size).toBe(7);
    expect(clusterCounts).toEqual(EXPECTED_CLUSTER_COUNTS);
    expect(OPAQUE_BACKGROUND_CONTRAST_SOURCES).toEqual(EXPECTED_SOURCES);
  });

  it("emits exactly seven computed passes only for complete numeric evidence", () => {
    const result = classifyOpaqueBackgroundContrast(passingObservations());

    expect(result.status).toBe("pass");
    expect(result.denominator).toBe(7);
    expect(result.passed).toBe(7);
    expect(result.failures).toEqual([]);
    expect(result.receipts).toHaveLength(7);
    expect(result.receipts.map(({ sourceId }) => sourceId)).toEqual(
      EXPECTED_SOURCES.map(({ sourceId }) => sourceId),
    );
    expect(result.receipts.every(({ result: receipt }) => receipt === "computed_pass")).toBe(
      true,
    );
  });

  it("keeps axe incomplete unattributed and emits zero receipts", () => {
    const result = classifyOpaqueBackgroundContrast(
      replaceObservation("badge-neutral", { incompleteCount: 1 }),
    );

    expect(result.status).toBe("fail");
    expect(result.passed).toBe(0);
    expect(result.receipts).toEqual([]);
    const failure = result.failures.find(
      ({ kind }) => kind === "axe_incomplete_unattributed",
    );
    expect(failure).toBeDefined();
    expect(failure).not.toHaveProperty("sourceId");
  });

  it("rejects zero violations when axe supplies no numeric pass", () => {
    const result = classifyOpaqueBackgroundContrast(
      replaceObservation("badge-neutral", { contrastPasses: [] }),
    );

    expect(result.status).toBe("fail");
    expect(result.receipts).toEqual([]);
    expect(result.failures).toContainEqual(
      expect.objectContaining({ kind: "pass_missing", sourceId: "badge-neutral" }),
    );
  });

  it("rejects a missing declared source", () => {
    const result = classifyOpaqueBackgroundContrast(
      passingObservations().filter(
        ({ sourceId }) => sourceId !== "time-semantics-label",
      ),
    );

    expect(result.status).toBe("fail");
    expect(result.receipts).toEqual([]);
    expect(result.failures).toContainEqual(
      expect.objectContaining({
        kind: "source_missing",
        sourceId: "time-semantics-label",
      }),
    );
  });

  it("rejects duplicate and unknown source identities", () => {
    const observations = passingObservations();
    observations[1] = { ...observations[0] };
    observations[2] = { ...observations[2], sourceId: "invented-source" };

    const result = classifyOpaqueBackgroundContrast(observations);

    expect(result.status).toBe("fail");
    expect(result.receipts).toEqual([]);
    expect(result.failures.map(({ kind }) => kind)).toEqual(
      expect.arrayContaining(["source_duplicate", "source_unknown"]),
    );
  });

  it("rejects missing or nonnumeric ratio data", () => {
    const result = classifyOpaqueBackgroundContrast(
      replaceObservation("candidate-frame", {
        contrastPasses: [
          { contrastRatio: undefined, expectedContrastRatio: "4.5:1" },
        ],
      }),
    );

    expect(result.status).toBe("fail");
    expect(result.receipts).toEqual([]);
    expect(result.failures).toContainEqual(
      expect.objectContaining({ kind: "ratio_invalid", sourceId: "candidate-frame" }),
    );
  });

  it("rejects a numeric result below axe's required ratio", () => {
    const result = classifyOpaqueBackgroundContrast(
      replaceObservation("negative-certificate-card", {
        contrastPasses: [{ contrastRatio: 3.2, expectedContrastRatio: 4.5 }],
      }),
    );

    expect(result.status).toBe("fail");
    expect(result.receipts).toEqual([]);
    expect(result.failures).toContainEqual(
      expect.objectContaining({
        kind: "ratio_below_required",
        sourceId: "negative-certificate-card",
      }),
    );
  });

  it("rejects a retained source marker when the backdrop is not opaque", () => {
    const result = classifyOpaqueBackgroundContrast(
      replaceObservation("weakest-link-explainer", { opaqueBackdrop: false }),
    );

    expect(result.status).toBe("fail");
    expect(result.receipts).toEqual([]);
    expect(result.failures).toContainEqual(
      expect.objectContaining({
        kind: "backdrop_not_opaque",
        sourceId: "weakest-link-explainer",
      }),
    );
  });

  it("recomputes opacity from a marker-retaining DOM surface", () => {
    const surface = document.createElement("section");
    surface.dataset.opaqueContrastSource = "weakest-link-explainer";
    surface.style.backgroundImage = "none";
    surface.style.backgroundColor = "rgba(255, 255, 255, 0.65)";
    document.body.append(surface);

    expect(hasOpaqueBackground(surface)).toBe(false);

    surface.style.backgroundColor = "rgb(255, 255, 255)";
    expect(hasOpaqueBackground(surface)).toBe(true);
    surface.remove();
  });

  it("rejects malformed violation and incomplete counts", () => {
    for (const replacement of [
      { incompleteCount: Number.NaN },
      { incompleteCount: -1 },
      { incompleteCount: 0.5 },
      { violationCount: Number.NaN },
      { violationCount: -1 },
      { violationCount: 0.5 },
    ]) {
      const result = classifyOpaqueBackgroundContrast(
        replaceObservation("badge-neutral", replacement),
      );

      expect(result.status).toBe("fail");
      expect(result.receipts).toEqual([]);
      expect(result.failures).toContainEqual(
        expect.objectContaining({ kind: "count_invalid", sourceId: "badge-neutral" }),
      );
    }
  });

  it("exposes the browser adapter without executing its browser lane", async () => {
    const story = await import("./OpaqueBackgroundContrast.stories");

    expect(story.SevenDeclaredSources.play).toBeTypeOf("function");
  });
});
