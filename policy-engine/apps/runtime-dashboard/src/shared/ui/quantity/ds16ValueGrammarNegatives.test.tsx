import { describe, expect, it } from "vitest";

import type { ObservationProvenanceClass } from "@/test/contracts/quantityDecisionProducerHarness";
import {
  GAP_STATE_TOKEN,
  NO_ADMISSIBLE_RANKING_TOKEN,
  outerSetMembers,
  renderDerivedSeriesWithProvenanceClass,
  renderDerivedSeriesWithoutProvenanceClass,
  renderGapAsZero,
  renderIncomparableAsFrontier,
  renderIncomparableAsRanking,
  renderModelOutputAsModelOutput,
  renderModelOutputStyledAsObserved,
  renderOuterSetAsSet,
  renderOuterSetCollapsedToPoint,
  renderThreeDistinctValueStates,
  renderUnknownAsGap,
  renderUnknownAsZero,
} from "@/test/contracts/quantityDecisionProducerHarness";
import { renderWithProviders } from "@/test/render";

/**
 * DS16-C01 — the value-grammar negatives, written before any producer byte.
 *
 * Every negative here is proved NON-VACUOUS in its own `it`: the guard is run
 * against the compliant render (expected empty) and against a deliberately
 * violating fixture (expected non-empty). A guard that cannot report a finding
 * on demand is decoration, not a negative — that is the `P29` authorial-proof
 * failure in test clothing, and it is the specific risk this cluster exists to
 * retire.
 *
 * Register IDs are named per negative in its `it` title and in the comments.
 */

type Findings = readonly string[];

function markup(node: ReturnType<typeof renderOuterSetAsSet>) {
  const view = renderWithProviders(node);
  const container = view.container;
  return { container, unmount: () => view.unmount() };
}

// -- negative 1 (`P05`/`P10`) ------------------------------------------------

function setCollapseFindings(
  container: HTMLElement,
  memberCount: number,
): Findings {
  const findings: string[] = [];
  const declared = container
    .querySelector("[data-chart-quantity-cardinality]")
    ?.getAttribute("data-chart-quantity-cardinality");
  if (declared !== String(memberCount)) {
    findings.push(`cardinality-not-declared:${declared ?? "absent"}`);
  }
  const scalars = container.querySelectorAll(
    '[data-quantity-presentation="scalar"]',
  );
  if (memberCount > 1 && scalars.length < memberCount) {
    findings.push(`set-rendered-as-point:${scalars.length}`);
  }
  return findings;
}

// -- negative 2 (`P10`) ------------------------------------------------------

function provenanceMarkingFindings(container: HTMLElement): Findings {
  const series = container.querySelector(
    '[data-testid="ds16-provenance-series"]',
  );
  if (!series) {
    return ["provenance-series-missing"];
  }
  return series.getAttribute("data-observation-class") === null
    ? ["provenance-class-unmarked"]
    : [];
}

// -- negative 3 (`P15`, data plane) ------------------------------------------

function modelOutputStylingFindings(
  container: HTMLElement,
  declared: ObservationProvenanceClass,
): Findings {
  const rendered = container
    .querySelector('[data-testid="ds16-provenance-series"]')
    ?.getAttribute("data-observation-class");
  if (declared === "model_output" && rendered !== "model_output") {
    return [`model-output-styled-as:${rendered ?? "absent"}`];
  }
  return [];
}

// -- negative 5 (`P10`) ------------------------------------------------------

function renderedValueSignatures(container: HTMLElement): Findings {
  return [...container.querySelectorAll('[data-testid="ds16-value-state"]')].map(
    (cell) => {
      const quantity = cell.querySelector("[data-quantity-presentation]");
      const presentation =
        quantity?.getAttribute("data-quantity-presentation") ?? "absent";
      return `${presentation}:${(quantity?.textContent ?? "").trim()}`;
    },
  );
}

function collapsedStateFindings(
  container: HTMLElement,
  declaredStates: readonly string[],
): Findings {
  const rendered = renderedValueSignatures(container);
  const findings: string[] = [];
  for (let left = 0; left < rendered.length; left += 1) {
    for (let right = left + 1; right < rendered.length; right += 1) {
      if (rendered[left] === rendered[right]) {
        findings.push(
          `states-collapsed:${declaredStates[left]}~${declaredStates[right]}:${rendered[left]}`,
        );
      }
    }
  }
  return findings;
}

// -- negative 6 (`P05`/`P10`) ------------------------------------------------

function rankingFindings(container: HTMLElement): Findings {
  const comparison = container.querySelector('[data-testid="ds16-comparison"]');
  if (!comparison) {
    return ["comparison-missing"];
  }
  const findings: string[] = [];
  if (comparison.tagName.toLowerCase() === "ol") {
    findings.push("ordered-list-semantics");
  }
  if (comparison.querySelector("[data-rank]")) {
    findings.push("rank-position-rendered");
  }
  if (comparison.querySelector("[aria-posinset]")) {
    findings.push("set-position-rendered");
  }
  return findings;
}

describe("DS16-C01 value-grammar negatives", () => {
  it("negative 1 (P05/P10): a set-valued value rendered as a point estimate fails", () => {
    const compliant = markup(renderOuterSetAsSet());
    expect(
      setCollapseFindings(compliant.container, outerSetMembers.length),
    ).toEqual([]);
    compliant.unmount();

    // The violating fixture averages the supports into one scalar.
    const violating = markup(renderOuterSetCollapsedToPoint());
    expect(
      setCollapseFindings(violating.container, outerSetMembers.length),
    ).toEqual(["cardinality-not-declared:absent", "set-rendered-as-point:1"]);
    violating.unmount();
  });

  it("negative 2 (P10): a derived series rendered without its provenance class fails", () => {
    const compliant = markup(renderDerivedSeriesWithProvenanceClass());
    expect(provenanceMarkingFindings(compliant.container)).toEqual([]);
    compliant.unmount();

    const violating = markup(renderDerivedSeriesWithoutProvenanceClass());
    expect(provenanceMarkingFindings(violating.container)).toEqual([
      "provenance-class-unmarked",
    ]);
    violating.unmount();
  });

  it("negative 3 (P15): a class-(iv) model output styled as observed data fails", () => {
    const compliant = markup(renderModelOutputAsModelOutput());
    expect(
      modelOutputStylingFindings(compliant.container, "model_output"),
    ).toEqual([]);
    compliant.unmount();

    // `overlay.py:84-90` makes model_output the fourth ObservationProvenanceClass
    // member — the master plan's "class-(iv)" — and `acquisition_executor.py:1719`
    // refuses its admission as an observation.
    const violating = markup(renderModelOutputStyledAsObserved());
    expect(
      modelOutputStylingFindings(violating.container, "model_output"),
    ).toEqual(["model-output-styled-as:observed"]);
    violating.unmount();
  });

  it("negative 5 (P10): unknown rendered as zero, or as a gap, fails — three states, not two", () => {
    const declared = ["zero", "unknown", "gap"] as const;

    const compliant = markup(renderThreeDistinctValueStates());
    expect(renderedValueSignatures(compliant.container)).toHaveLength(3);
    expect(new Set(renderedValueSignatures(compliant.container)).size).toBe(3);
    expect(collapsedStateFindings(compliant.container, declared)).toEqual([]);
    compliant.unmount();

    // Each of the three collapses is a separate RED — the negative separates
    // all three states, never only zero-from-missing.
    const asZero = markup(renderUnknownAsZero());
    expect(
      collapsedStateFindings(asZero.container, ["zero", "unknown", "gap"]),
    ).toEqual(["states-collapsed:zero~unknown:scalar:0"]);
    asZero.unmount();

    const asGap = markup(renderUnknownAsGap());
    expect(
      collapsedStateFindings(asGap.container, ["zero", "unknown", "gap"]),
    ).toEqual([
      `states-collapsed:unknown~gap:non-scalar:${GAP_STATE_TOKEN}`,
    ]);
    asGap.unmount();

    const gapAsZero = markup(renderGapAsZero());
    expect(
      collapsedStateFindings(gapAsZero.container, ["zero", "unknown", "gap"]),
    ).toEqual(["states-collapsed:zero~gap:scalar:0"]);
    gapAsZero.unmount();
  });

  it("negative 6 (P05/P10): incomparable rendered as a ranking fails", () => {
    const compliant = markup(renderIncomparableAsFrontier());
    expect(rankingFindings(compliant.container)).toEqual([]);
    expect(compliant.container.textContent).toContain(
      NO_ADMISSIBLE_RANKING_TOKEN,
    );
    compliant.unmount();

    const violating = markup(renderIncomparableAsRanking());
    expect(rankingFindings(violating.container)).toEqual([
      "ordered-list-semantics",
      "rank-position-rendered",
      "set-position-rendered",
    ]);
    violating.unmount();
  });
});
