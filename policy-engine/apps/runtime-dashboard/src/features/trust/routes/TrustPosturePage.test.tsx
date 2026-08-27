import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

const artifactBytes = readFileSync(
  resolve(process.cwd(), "public/atlas/trust-claim-posture.v1.json"),
);
const identityDocument = readFileSync(
  resolve(
    process.cwd(),
    "../../docs/system-design-decisions/policyos-identity-and-custody-boundary.md",
  ),
  "utf8",
);

function deriveRatifiedIdentity() {
  const statementSection = identityDocument.match(
    /## 1\. The decision in one sentence\s+(.+?)\s+## 2\./su,
  )?.[1];
  const statement = statementSection?.match(/\*\*(.+?)\*\*/su)?.[1];
  const paragraph = identityDocument.match(
    /\*\*Anti-roles \(binding\):\*\*\s*(.+?)(?:\n\n|$)/su,
  )?.[1];
  if (!statement || !paragraph) {
    throw new TypeError("ratified identity source is malformed");
  }
  const normalizedParagraph = paragraph.split(/\s+/u).join(" ");
  const roleSentence = `${normalizedParagraph.split(".", 1)[0]}.`;
  const antiRoles = [...roleSentence.matchAll(/\bnot (?:an? )?(.+?)(?=, not |,? or not |\.)/gu)].map(
    (match) => match[1]!.trim().replace(/\.$/u, ""),
  );
  return { antiRoles, statement };
}

const ratifiedIdentity = deriveRatifiedIdentity();

describe("TrustPosturePage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("defaults to PUBLIC and keeps claim-bearing values fixed across depth", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.resolve(new Response(artifactBytes, { status: 200 }))),
    );
    const { default: TrustPosturePage } = await import("./TrustPosturePage");
    const view = renderWithProviders(<TrustPosturePage />, {
      initialEntries: ["/trust"],
    });

    expect(await screen.findByTestId("trust-posture-page")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        view.container.querySelectorAll("[data-trust-claim-row]").length,
      ).toBeGreaterThan(0),
    );
    expect(screen.getByRole("button", { name: "Public" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    const claimBearingBefore = [
      ...view.container.querySelectorAll("[data-trust-claim-bearing]"),
    ].map((node) => node.textContent);
    fireEvent.click(screen.getByRole("button", { name: "Reviewer" }));
    const claimBearingAfter = [
      ...view.container.querySelectorAll("[data-trust-claim-bearing]"),
    ].map((node) => node.textContent);
    expect(claimBearingAfter).toEqual(claimBearingBefore);
    expect(
      view.container.querySelectorAll("[data-trust-evidence-detail]").length,
    ).toBeGreaterThan(0);
    expect(
      view.container.querySelector("[data-trust-evidence-values]"),
    ).toBeVisible();
    expect(screen.getByTestId("trust-identity-statement").textContent).toBe(
      ratifiedIdentity.statement,
    );
    expect(
      [...view.container.querySelectorAll("[data-trust-anti-role]")].map(
        (node) => node.textContent,
      ),
    ).toEqual(ratifiedIdentity.antiRoles);
    expect(ratifiedIdentity.antiRoles).toHaveLength(7);
  });

  it("fails visibly unavailable instead of retaining a previous posture", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.resolve(new Response("{}", { status: 200 }))),
    );
    const { default: TrustPosturePage } = await import("./TrustPosturePage");
    renderWithProviders(<TrustPosturePage />, { initialEntries: ["/trust"] });

    expect(
      await screen.findByTestId("trust-posture-unavailable"),
    ).toHaveTextContent(/unavailable/i);
    expect(screen.queryByTestId("trust-posture-register")).toBeNull();
  });
});
