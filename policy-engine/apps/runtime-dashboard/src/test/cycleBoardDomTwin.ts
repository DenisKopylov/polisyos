import type { VisibleCycleBoard } from "@/features/runs/components/cycleBoardPresentation";

type VisibleRow = VisibleCycleBoard["rows"][number];

const ROW_FACT_FIELDS = [
  "searchTerminalKind",
  "lifecycleTerminality",
  "structuralEvidenceClass",
  "weakestLinks",
  "missingLink",
  "acquisitionRoute",
  "acquisitionEconomics",
  "generationCycleRunId",
  "designProblem",
  "surfaceReadiness",
  "stageTraceHref",
] as const satisfies ReadonlyArray<keyof VisibleRow>;

function elements(root: ParentNode, selector: string): HTMLElement[] {
  return Array.from(root.querySelectorAll(selector)).map((node) => {
    if (!(node instanceof HTMLElement)) {
      throw new TypeError(`Cycle Board DOM region is not HTML: ${selector}`);
    }
    return node;
  });
}

function singleton(root: ParentNode, selector: string): HTMLElement {
  const matches = elements(root, selector);
  if (matches.length !== 1) {
    throw new Error(
      `Cycle Board DOM requires exactly one ${selector}; found ${matches.length}`,
    );
  }
  return matches[0] as HTMLElement;
}

function readRaw(element: HTMLElement, label: string): unknown {
  const encoded = element.getAttribute("data-cycle-board-raw");
  if (encoded === null) {
    throw new Error(`Cycle Board DOM region has no raw payload: ${label}`);
  }
  try {
    return JSON.parse(encoded) as unknown;
  } catch (error) {
    throw new Error(`Cycle Board DOM raw payload is invalid: ${label}`, {
      cause: error,
    });
  }
}

function canonicalJson(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(canonicalJson);
  }
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, member]) => [key, canonicalJson(member)]),
    );
  }
  return value;
}

function encoded(value: unknown): string {
  return JSON.stringify(canonicalJson(value));
}

function requireEqual(actual: unknown, expected: unknown, label: string) {
  if (encoded(actual) !== encoded(expected)) {
    throw new Error(`Cycle Board DOM mismatch: ${label}`);
  }
}

function factAvailability(value: unknown): string | null {
  if (!value || typeof value !== "object" || !("availability" in value)) {
    return null;
  }
  const availability = (value as { availability?: unknown }).availability;
  return typeof availability === "string" ? availability : null;
}

function decodeRow(element: HTMLElement): VisibleRow {
  const row = readRaw(element, "row") as VisibleRow;
  if (element.getAttribute("data-row-id") !== row.rowId) {
    throw new Error(`Cycle Board DOM row identity mismatch: ${row.rowId}`);
  }

  const fieldNodes = elements(element, "[data-cycle-board-field]");
  const fieldIds = fieldNodes.map((node) =>
    node.getAttribute("data-cycle-board-field"),
  );
  const expectedFieldIds = [...ROW_FACT_FIELDS, "public-safe-explanation"];
  requireEqual(
    [...fieldIds].sort(),
    [...expectedFieldIds].sort(),
    `${row.rowId} field population`,
  );

  for (const field of ROW_FACT_FIELDS) {
    const node = singleton(element, `[data-cycle-board-field="${field}"]`);
    const fact = readRaw(
      node,
      `${row.rowId}.${field}`,
    ) as VisibleRow[typeof field];
    requireEqual(fact, row[field], `${row.rowId}.${field}`);
    if (node.getAttribute("data-availability") !== factAvailability(fact)) {
      throw new Error(
        `Cycle Board DOM availability mismatch: ${row.rowId}.${field}`,
      );
    }
  }

  const explanation = readRaw(
    singleton(element, '[data-cycle-board-field="public-safe-explanation"]'),
    `${row.rowId}.public-safe-explanation`,
  ) as {
    explanation_code: string;
    explanation_inputs: unknown;
  };
  requireEqual(
    explanation,
    {
      explanation_code: row.explanationCode,
      explanation_inputs: row.explanationInputs,
    },
    `${row.rowId}.public-safe-explanation`,
  );

  const movements = elements(element, "[data-cycle-board-movement]").map(
    (node, index) =>
      readRaw(node, `${row.rowId}.movementRecords[${String(index)}]`),
  );
  requireEqual(movements, row.movementRecords, `${row.rowId}.movementRecords`);

  const stageTraceLinks = elements(element, "details a");
  if (row.stageTraceHref.availability === "available") {
    if (
      stageTraceLinks.length !== 1 ||
      stageTraceLinks[0]?.getAttribute("href") !== row.stageTraceHref.value
    ) {
      throw new Error(`Cycle Board DOM stage-trace mismatch: ${row.rowId}`);
    }
  } else if (stageTraceLinks.length !== 0) {
    throw new Error(`Cycle Board DOM fabricated stage trace: ${row.rowId}`);
  }

  return row;
}

/** Decode the complete Cycle Board value from rendered semantic DOM regions. */
export function decodeCycleBoardDom(container: HTMLElement): VisibleCycleBoard {
  const packetNode = singleton(container, "[data-cycle-board-packet]");
  const packet = readRaw(packetNode, "packet") as VisibleCycleBoard["packet"];
  if (
    packetNode.getAttribute("data-audiences") !==
    packet.intendedAudiences.join(",")
  ) {
    throw new Error("Cycle Board DOM audience mismatch");
  }

  const coverageNode = singleton(
    container,
    '[data-cycle-board-gap="coverage"]',
  );
  const coverage = readRaw(
    coverageNode,
    "coverage",
  ) as VisibleCycleBoard["coverage"];
  if (
    coverageNode.getAttribute("data-exhaustive") !==
      String(coverage.exhaustive) ||
    coverageNode.getAttribute("data-known-row-count") !==
      String(coverage.known_row_count)
  ) {
    throw new Error("Cycle Board DOM coverage metadata mismatch");
  }

  const movementGap = readRaw(
    singleton(container, '[data-cycle-board-gap="movement"]'),
    "movement gap",
  ) as VisibleCycleBoard["movementGap"];
  const realizedDs4Disposition = readRaw(
    singleton(container, '[data-cycle-board-summary="ds4-disposition"]'),
    "DS4 disposition",
  ) as VisibleCycleBoard["realizedDs4Disposition"];
  const historicalProducerAvailability = readRaw(
    singleton(
      container,
      '[data-cycle-board-summary="historical-producer-availability"]',
    ),
    "historical producer availability",
  ) as VisibleCycleBoard["historicalProducerAvailability"];

  const sources = elements(container, "[data-cycle-board-source]").map(
    (node, index) => {
      const source = readRaw(
        node,
        `sources[${String(index)}]`,
      ) as VisibleCycleBoard["sources"][number];
      if (
        node.getAttribute("data-source-id") !== source.source_id ||
        node.getAttribute("data-availability") !== source.availability
      ) {
        throw new Error(
          `Cycle Board DOM source identity mismatch: ${String(index)}`,
        );
      }
      return source;
    },
  );

  const rows = elements(container, "[data-cycle-board-row]").map(decodeRow);
  const cohortTransitions = rows
    .filter((row, index) => rows[index - 1]?.cohort !== row.cohort)
    .map((row) => ({ cohort: row.cohort }));
  const renderedCohorts = elements(container, "[data-cycle-board-cohort]").map(
    (node, index) =>
      readRaw(node, `cohorts[${String(index)}]`) as { cohort: string },
  );
  requireEqual(renderedCohorts, cohortTransitions, "cohort transitions");

  return {
    coverage,
    historicalProducerAvailability,
    movementGap,
    packet,
    realizedDs4Disposition,
    rows,
    sources,
  };
}
