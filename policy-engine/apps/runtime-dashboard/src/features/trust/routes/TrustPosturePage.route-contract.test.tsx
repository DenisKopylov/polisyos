import { Suspense } from "react";

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

describe("trust public route contract", () => {
  it("declares the exact static /trust route through APP_ROUTES", async () => {
    const [{ APP_ROUTES }, { trustRoute, trustRouteHandle }] =
      await Promise.all([
        import("@/app/routes/routes"),
        import("@/features/trust/routes.public"),
      ]);
    const appFrame = APP_ROUTES.find((route) => route.path === "/");
    const matchingChildren =
      appFrame?.children?.filter((route) => route === trustRoute) ?? [];

    expect(matchingChildren).toHaveLength(1);
    expect(trustRoute.path).toBe("trust");
    expect(trustRoute.loader).toBeUndefined();
    expect(trustRouteHandle.buildHref()).toBe("/trust");
    expect(trustRouteHandle).not.toHaveProperty("prefetch");
    expect(trustRouteHandle).not.toHaveProperty("workspaceKey");
  });

  it("links exactly once from landing with a neutral interface label", async () => {
    const { landingRoute } = await import("@/features/landing");
    const view = render(
      <MemoryRouter>
        <LocaleProvider>
          <Suspense fallback={null}>{landingRoute.element}</Suspense>
        </LocaleProvider>
      </MemoryRouter>,
    );

    await screen.findByRole("link", { name: "Trust posture" });

    // eslint-disable-next-line testing-library/no-container, testing-library/no-node-access -- The route contract counts every exact href, including duplicate or hidden anchors.
    const links = view.container.querySelectorAll('a[href="/trust"]');
    expect(links).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Trust posture" })).toBeVisible();
  });
});
