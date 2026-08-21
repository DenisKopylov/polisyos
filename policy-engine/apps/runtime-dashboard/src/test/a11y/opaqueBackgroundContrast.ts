export const OPAQUE_BACKGROUND_CONTRAST_SOURCES = [
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

export type OpaqueBackgroundContrastSource =
  (typeof OPAQUE_BACKGROUND_CONTRAST_SOURCES)[number];
export type OpaqueBackgroundContrastSourceId =
  OpaqueBackgroundContrastSource["sourceId"];

export type AxeContrastPass = {
  contrastRatio: unknown;
  expectedContrastRatio: unknown;
};

export type OpaqueBackgroundContrastObservation = {
  sourceId: string;
  opaqueBackdrop: boolean;
  violationCount: number;
  incompleteCount: number;
  contrastPasses: AxeContrastPass[];
};

type SourceFailureKind =
  | "backdrop_not_opaque"
  | "count_invalid"
  | "pass_missing"
  | "ratio_below_required"
  | "ratio_invalid"
  | "source_duplicate"
  | "source_missing"
  | "violation_present";

export type OpaqueBackgroundContrastFailure =
  | {
      kind: "axe_incomplete_unattributed";
      detail: string;
    }
  | {
      kind: "observation_count_mismatch" | "receipt_count_mismatch";
      detail: string;
    }
  | {
      kind: "source_unknown";
      reportedSourceId: string;
      detail: string;
    }
  | {
      kind: SourceFailureKind;
      sourceId: OpaqueBackgroundContrastSourceId;
      detail: string;
    };

export type OpaqueBackgroundContrastReceipt = {
  sourceId: OpaqueBackgroundContrastSourceId;
  ownerCluster: OpaqueBackgroundContrastSource["ownerCluster"];
  component: OpaqueBackgroundContrastSource["component"];
  result: "computed_pass";
  opaqueBackdrop: true;
  contrastPasses: Array<{
    contrastRatio: number;
    expectedContrastRatio: number;
  }>;
};

export type OpaqueBackgroundContrastClassification = {
  status: "pass" | "fail";
  denominator: number;
  passed: number;
  receipts: OpaqueBackgroundContrastReceipt[];
  failures: OpaqueBackgroundContrastFailure[];
};

const SOURCE_BY_ID = new Map<string, OpaqueBackgroundContrastSource>(
  OPAQUE_BACKGROUND_CONTRAST_SOURCES.map((source) => [source.sourceId, source]),
);

/** Recomputes the controlled opaque-background predicate from rendered DOM. */
export function hasOpaqueBackground(element: HTMLElement): boolean {
  const style = element.ownerDocument.defaultView?.getComputedStyle(element);
  if (!style || style.backgroundImage !== "none") {
    return false;
  }
  return backgroundAlpha(style.backgroundColor) === 1;
}

/**
 * Converts real-browser axe observations into an atomic seven-source receipt.
 *
 * A failed run emits no partial receipts. Incomplete axe results remain
 * deliberately unattributed because axe could not establish their source
 * contrast predicate.
 */
export function classifyOpaqueBackgroundContrast(
  observations: OpaqueBackgroundContrastObservation[],
): OpaqueBackgroundContrastClassification {
  const denominator = OPAQUE_BACKGROUND_CONTRAST_SOURCES.length;
  const failures: OpaqueBackgroundContrastFailure[] = [];
  const receipts: OpaqueBackgroundContrastReceipt[] = [];
  const seen = new Set<OpaqueBackgroundContrastSourceId>();

  if (observations.length !== denominator) {
    failures.push({
      kind: "observation_count_mismatch",
      detail: `Expected ${denominator} observations, received ${observations.length}.`,
    });
  }

  for (const observation of observations) {
    const source = SOURCE_BY_ID.get(observation.sourceId);
    if (!source) {
      failures.push({
        kind: "source_unknown",
        reportedSourceId: observation.sourceId,
        detail: "The observation identity is not in the frozen source registry.",
      });
      continue;
    }

    if (seen.has(source.sourceId)) {
      failures.push({
        kind: "source_duplicate",
        sourceId: source.sourceId,
        detail: "The source identity was observed more than once.",
      });
      continue;
    }
    seen.add(source.sourceId);

    if (
      !Number.isInteger(observation.incompleteCount) ||
      observation.incompleteCount < 0 ||
      !Number.isInteger(observation.violationCount) ||
      observation.violationCount < 0
    ) {
      failures.push({
        kind: "count_invalid",
        sourceId: source.sourceId,
        detail: "Violation and incomplete counts must be finite non-negative integers.",
      });
      continue;
    }

    if (observation.incompleteCount > 0) {
      failures.push({
        kind: "axe_incomplete_unattributed",
        detail: `Axe returned ${observation.incompleteCount} incomplete color-contrast result(s).`,
      });
      continue;
    }

    let sourceFailed = false;
    if (!observation.opaqueBackdrop) {
      failures.push({
        kind: "backdrop_not_opaque",
        sourceId: source.sourceId,
        detail: "The controlled background predicate was not established.",
      });
      sourceFailed = true;
    }
    if (observation.violationCount > 0) {
      failures.push({
        kind: "violation_present",
        sourceId: source.sourceId,
        detail: `Axe returned ${observation.violationCount} color-contrast violation(s).`,
      });
      sourceFailed = true;
    }
    if (observation.contrastPasses.length === 0) {
      failures.push({
        kind: "pass_missing",
        sourceId: source.sourceId,
        detail: "Zero violations alone is not evidence; axe emitted no numeric pass.",
      });
      sourceFailed = true;
    }

    const numericPasses: OpaqueBackgroundContrastReceipt["contrastPasses"] = [];
    for (const pass of observation.contrastPasses) {
      if (
        typeof pass.contrastRatio !== "number" ||
        !Number.isFinite(pass.contrastRatio) ||
        typeof pass.expectedContrastRatio !== "number" ||
        !Number.isFinite(pass.expectedContrastRatio) ||
        pass.expectedContrastRatio <= 0
      ) {
        failures.push({
          kind: "ratio_invalid",
          sourceId: source.sourceId,
          detail: "Axe pass data must contain finite numeric actual and required ratios.",
        });
        sourceFailed = true;
        continue;
      }
      if (pass.contrastRatio < pass.expectedContrastRatio) {
        failures.push({
          kind: "ratio_below_required",
          sourceId: source.sourceId,
          detail: `Contrast ${pass.contrastRatio}:1 is below ${pass.expectedContrastRatio}:1.`,
        });
        sourceFailed = true;
        continue;
      }
      numericPasses.push({
        contrastRatio: pass.contrastRatio,
        expectedContrastRatio: pass.expectedContrastRatio,
      });
    }

    if (!sourceFailed) {
      receipts.push({
        sourceId: source.sourceId,
        ownerCluster: source.ownerCluster,
        component: source.component,
        result: "computed_pass",
        opaqueBackdrop: true,
        contrastPasses: numericPasses,
      });
    }
  }

  for (const source of OPAQUE_BACKGROUND_CONTRAST_SOURCES) {
    if (!seen.has(source.sourceId)) {
      failures.push({
        kind: "source_missing",
        sourceId: source.sourceId,
        detail: "The declared source identity has no browser observation.",
      });
    }
  }

  if (receipts.length !== denominator && failures.length === 0) {
    failures.push({
      kind: "receipt_count_mismatch",
      detail: `Expected ${denominator} receipts, produced ${receipts.length}.`,
    });
  }

  if (failures.length > 0) {
    return {
      status: "fail",
      denominator,
      passed: 0,
      receipts: [],
      failures,
    };
  }

  const receiptById = new Map(receipts.map((receipt) => [receipt.sourceId, receipt]));
  return {
    status: "pass",
    denominator,
    passed: denominator,
    receipts: OPAQUE_BACKGROUND_CONTRAST_SOURCES.map(
      ({ sourceId }) => receiptById.get(sourceId)!,
    ),
    failures: [],
  };
}

function backgroundAlpha(color: string): number | null {
  if (color === "transparent") {
    return 0;
  }
  const commaRgba = color.match(
    /^rgba\([^,]+,[^,]+,[^,]+,\s*(0|1|0?\.\d+)\s*\)$/,
  );
  if (commaRgba) {
    return Number(commaRgba[1]);
  }
  const slashAlpha = color.match(/\/\s*(0|1|0?\.\d+)(?:%?)\s*\)$/);
  if (slashAlpha) {
    const value = Number(slashAlpha[1]);
    return color.includes("%") ? value / 100 : value;
  }
  return color.startsWith("rgb(") || color.startsWith("color(") ? 1 : null;
}
