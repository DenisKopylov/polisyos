import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmailSummary, renderEmailPlainText } from "./EmailSummary";
import {
  compareShareFixture,
  emailFixtures,
  runShareFixture,
  scenarioShareFixture,
} from "./email-fixtures";
import {
  generateOgHtml,
  generateOgMetadata,
  generateOgPng,
  generateOgSvg,
} from "./generate-og";
import { OGCard, sanitizePublicShareSummary } from "./OGCard";

describe("share templates", () => {
  it("renders an OG card with trust status and temporal scope", () => {
    const summary = sanitizePublicShareSummary({
      ...runShareFixture,
      epochSemantics: {
        asOf: null,
        asOfReason: "epoch_projection_not_established",
        currentEpochRef: null,
        epochRefs: [],
        kind: "nonreceipt",
        projectionSemanticHash: null,
        revalidationRequired: false,
        status: "not_established",
        validityStatus: null,
      },
    } as Parameters<typeof sanitizePublicShareSummary>[0]);
    render(<OGCard summary={summary} />);

    expect(screen.getByText("Reject or replan")).toBeInTheDocument();
    expect(screen.getByText("untraced")).toBeInTheDocument();
    expect(screen.getByText(/valid 2026-04-15/)).toBeInTheDocument();
    expect(summary).toHaveProperty("epochSemantics.kind", "nonreceipt");
    expect(screen.getByText(/Epoch not established/u)).toBeInTheDocument();
  });

  it("renders email html and plain text without raw sources", () => {
    const payload = {
      ...scenarioShareFixture,
      rawSources: ["private source text"],
    };
    const summary = sanitizePublicShareSummary(payload);
    const text = renderEmailPlainText(summary);
    render(<EmailSummary summary={summary} />);

    expect(screen.getByText("Rate cut 25 bps")).toBeInTheDocument();
    expect(text).toContain("Public summary only");
    expect(text).not.toContain("private source text");
  });

  it("keeps email summaries readable in narrow containers", () => {
    render(
      <div style={{ width: 320 }}>
        <EmailSummary summary={compareShareFixture} />
      </div>,
    );

    expect(screen.getByText("Policy diff")).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveStyle({ width: "100%" });
  });

  it("generates deterministic OG HTML, SVG and PNG metadata from public payloads", async () => {
    for (const fixture of Object.values(emailFixtures)) {
      const html = generateOgHtml(fixture);
      const svg = await generateOgSvg(fixture);
      const png = await generateOgPng(fixture);
      const metadata = generateOgMetadata(fixture);

      expect(html).toContain("PolicyOS Runtime");
      expect(svg).toContain("PolicyOS Runtime");
      expect(html).toContain(fixture.title);
      expect(svg).toContain(fixture.temporalScope.txAt ?? "known latest");
      expect(png.byteLength).toBeGreaterThan(10_000);
      expect(metadata.contentType).toBe("image/png");
      expect(metadata.shareHash).toHaveLength(64);
      expect(html).not.toContain("rawSources");
      expect(svg).not.toContain("rawSources");
    }
  });
});
