import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/render";

import { PublicSectorReadinessPanel } from "./PublicSectorReadinessPanel";
import { ScientificDepthPanel } from "./ScientificDepthPanel";

/**
 * DS16-C05 — the two behavioural properties C02 could not carry.
 *
 * C02's gate is structural. It named these two and assigned them here, because no AST
 * can decide either one:
 *
 *   1. TYPED REFUSAL AT RUNTIME. A bound panel whose producer supplies no value must
 *      render the typed refusal. Writable now only because C03 serves a
 *      `RefusedAuthorityValue` with a discriminated `state` rather than an absent key —
 *      an optional field is how "unavailable" silently becomes "zero".
 *   2. THE LABEL-CHANNEL CARRIER. C02 ruled key SELECTION structurally closed but key
 *      IDENTITY a bounded declared limitation: nothing in the AST separates
 *      `t("readiness.high")` from `t("readiness.sectionTitle")`, because the difference
 *      lives in DS6's catalog. The named divergence is a reviewer approving a
 *      value-bearing key. The carrier is here: a panel that hardcodes a verdict renders
 *      the same text no matter what the producer served, and following the producer is
 *      a property only a running panel can demonstrate.
 */

const RUN_ID = "run-ds16-c05";
const ENDPOINT = "*/api/v1/runs/:runId/authority-values";

type Refusal = {
  owner_surface: string | null;
  reason: string;
  refusal_code: string;
  retired_from: string;
  state: "refused";
  surface: "readiness" | "scientific";
  value_id: string;
};

function refusal(overrides: Partial<Refusal> & { value_id: string }): Refusal {
  return {
    owner_surface: null,
    reason: `reason for ${overrides.value_id}`,
    refusal_code: "no_runtime_producer",
    retired_from: "apps/runtime-dashboard/src/features/runs/domain/x.ts",
    state: "refused",
    surface: "readiness",
    ...overrides,
  };
}

function serve(values: readonly Refusal[]) {
  server.use(
    http.get(ENDPOINT, () =>
      HttpResponse.json({
        inventory_version: "ds16-c05.1",
        retirement_commit: "bc1d01001",
        run_id: RUN_ID,
        values,
      }),
    ),
  );
}

describe("DS16-C05 bound panel behaviour", () => {
  it("renders the producer's typed refusal, with its reason and code, on the glass", async () => {
    serve([
      refusal({
        reason: "No governed artifact defines how a readiness verdict is composed.",
        refusal_code: "no_runtime_composition_rule",
        value_id: "readiness.composite_verdict",
      }),
      refusal({
        owner_surface: "atlas audience mapping (DS0/DS3)",
        reason: "Stakeholder-lens projection is audience mapping.",
        refusal_code: "owned_by_another_surface",
        value_id: "readiness.lens_projection",
      }),
    ]);

    renderWithProviders(<PublicSectorReadinessPanel runId={RUN_ID} />);

    const verdict = await screen.findByText(
      "No governed artifact defines how a readiness verdict is composed.",
    );
    // The refusal reaches the glass as a typed refusal: its state, its reason code and
    // its owning surface are all present, not flattened into a bare "unavailable".
    expect(verdict).toHaveAttribute("data-state", "refused");
    expect(verdict).toHaveAttribute(
      "data-refusal-code",
      "no_runtime_composition_rule",
    );
    expect(verdict).toHaveAttribute("data-value-id", "readiness.composite_verdict");

    const lens = screen.getByText("Stakeholder-lens projection is audience mapping.");
    expect(lens).toHaveAttribute("data-refusal-code", "owned_by_another_surface");
    expect(lens).toHaveAttribute(
      "data-owner-surface",
      "atlas audience mapping (DS0/DS3)",
    );
  });

  it("renders nothing beyond the sanctioned refusal when the producer serves no member", async () => {
    serve([]);

    const view = renderWithProviders(<PublicSectorReadinessPanel runId={RUN_ID} />);

    const panel = await screen.findByTestId("public-sector-readiness-panel");
    expect(panel).toHaveTextContent("Unavailable");
    // No invented placeholder row, and no zero.
    expect(
      view.container.querySelectorAll("[data-value-id]"),
      "an empty producer answer must not be padded with a placeholder",
    ).toHaveLength(0);
    expect(panel.textContent).not.toContain("0");
  });

  it("follows the producer rather than itself — the label-channel carrier", async () => {
    // A panel that hardcoded a verdict would render identically for both payloads.
    // Requiring the output to CHANGE with the producer is what catches it, and it is
    // a property no AST can check.
    serve([
      refusal({
        reason: "first producer answer",
        refusal_code: "no_runtime_estimator",
        value_id: "readiness.fairness_audit",
      }),
    ]);
    const first = renderWithProviders(<PublicSectorReadinessPanel runId={RUN_ID} />);
    await screen.findByText("first producer answer");
    expect(
      first.container.querySelector('[data-value-id="readiness.fairness_audit"]'),
    ).toHaveAttribute("data-refusal-code", "no_runtime_estimator");
    first.unmount();

    serve([
      refusal({
        reason: "second producer answer",
        refusal_code: "analysis_not_runtime_resident",
        value_id: "readiness.harm_assessment",
      }),
    ]);
    const second = renderWithProviders(<PublicSectorReadinessPanel runId={RUN_ID} />);
    await screen.findByText("second producer answer");

    // The first payload's content is gone: nothing was retained locally.
    expect(screen.queryByText("first producer answer")).not.toBeInTheDocument();
    expect(
      second.container.querySelector('[data-value-id="readiness.fairness_audit"]'),
    ).toBeNull();
    expect(
      second.container.querySelector('[data-value-id="readiness.harm_assessment"]'),
    ).toHaveAttribute("data-refusal-code", "analysis_not_runtime_resident");
  });

  it("renders only its own surface's members, on the producer's partition", async () => {
    serve([
      refusal({ surface: "readiness", value_id: "readiness.slow_review" }),
      refusal({ surface: "scientific", value_id: "scientific.stress_ranking" }),
    ]);

    const readiness = renderWithProviders(
      <PublicSectorReadinessPanel runId={RUN_ID} />,
    );
    await waitFor(() =>
      expect(
        readiness.container.querySelector('[data-value-id="readiness.slow_review"]'),
      ).not.toBeNull(),
    );
    expect(
      readiness.container.querySelector(
        '[data-value-id="scientific.stress_ranking"]',
      ),
    ).toBeNull();
    readiness.unmount();

    const scientific = renderWithProviders(<ScientificDepthPanel runId={RUN_ID} />);
    await waitFor(() =>
      expect(
        scientific.container.querySelector(
          '[data-value-id="scientific.stress_ranking"]',
        ),
      ).not.toBeNull(),
    );
    expect(
      scientific.container.querySelector('[data-value-id="readiness.slow_review"]'),
    ).toBeNull();
  });

  it("composes no summary over the refusals", async () => {
    serve([
      refusal({ value_id: "readiness.composite_verdict" }),
      refusal({ value_id: "readiness.fairness_audit" }),
      refusal({ value_id: "readiness.harm_assessment" }),
    ]);

    const view = renderWithProviders(<PublicSectorReadinessPanel runId={RUN_ID} />);
    await screen.findByText("reason for readiness.composite_verdict");

    // Eleven honest refusals are the product. A count, a share or a score over them is
    // the DS4-C23 sin rebuilt one layer up, so the glass carries no such number.
    const text = view.container.textContent ?? "";
    expect(text).not.toMatch(/\b3\b/u);
    expect(text).not.toMatch(/%/u);
    expect(text).not.toMatch(/\bof\s+\d/iu);
  });
});
