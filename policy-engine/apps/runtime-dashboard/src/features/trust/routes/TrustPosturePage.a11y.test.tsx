import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "vitest-axe";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

const artifactValue = JSON.parse(
  readFileSync(
    resolve(process.cwd(), "public/atlas/trust-claim-posture.v1.json"),
    "utf8",
  ),
) as {
  claims: Array<{ claim_id: string }>;
  projection_groups: Array<{ claim_ids: string[] }>;
  [key: string]: unknown;
};

describe("TrustPosturePage accessibility", () => {
  afterEach(() => {
    vi.doUnmock("@/features/trust/domain/loadPosture");
    vi.resetModules();
  });

  it("has labelled depth controls, visible limitations, and no axe violations", async () => {
    const selectedClaims = artifactValue.claims.slice(0, 5);
    const selectedIds = new Set(selectedClaims.map((claim) => claim.claim_id));
    const register = {
      ...artifactValue,
      claims: selectedClaims,
      projection_groups: artifactValue.projection_groups.map((group) => ({
        ...group,
        claim_ids: group.claim_ids.filter((claimId) => selectedIds.has(claimId)),
      })),
    };
    vi.doMock("@/features/trust/domain/loadPosture", () => ({
      loadPosture: vi.fn(async () => ({
        rawBytes: new Uint8Array([123, 125]),
        register,
        status: "available",
      })),
    }));
    const { default: TrustPosturePage } = await import("./TrustPosturePage");
    const view = render(
      <MemoryRouter initialEntries={["/trust"]}>
        <LocaleProvider>
          <TrustPosturePage />
        </LocaleProvider>
      </MemoryRouter>,
    );

    await screen.findByTestId("trust-posture-register");
    expect(screen.getByRole("group", { name: /detail/i })).toBeInTheDocument();
    expect(view.container.querySelector("[data-trust-limitation]")).toBeVisible();
    expect((await axe(view.container)).violations).toHaveLength(0);
  });
});
