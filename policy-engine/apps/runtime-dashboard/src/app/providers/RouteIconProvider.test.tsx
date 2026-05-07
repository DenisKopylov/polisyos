import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";

import {
  PRODUCT_FAVICON_HREF,
  PUBLIC_FAVICON_HREF,
  resolveBrandSurface,
  resolveFaviconHref,
  RouteIconProvider,
} from "./RouteIconProvider";

function currentFaviconHref() {
  return document
    .querySelector<HTMLLinkElement>('link[rel="icon"]')
    ?.getAttribute("href");
}

describe("RouteIconProvider", () => {
  beforeEach(() => {
    document.head.innerHTML =
      '<link id="app-favicon" rel="icon" type="image/svg+xml" href="/atlas/logo-mark.svg" />';
  });

  it("resolves public and product surfaces by pathname", () => {
    expect(resolveBrandSurface("/welcome")).toBe("public");
    expect(resolveBrandSurface("/login")).toBe("public");
    expect(resolveBrandSurface("/runs/run-1/overview")).toBe("product");
    expect(resolveFaviconHref("/welcome")).toBe(PUBLIC_FAVICON_HREF);
    expect(resolveFaviconHref("/runs")).toBe(PRODUCT_FAVICON_HREF);
  });

  it("switches favicon when route changes", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/welcome"]}>
        <RouteIconProvider />
        <Routes>
          <Route
            path="/welcome"
            element={<Link to="/runs">Open product</Link>}
          />
          <Route path="/runs" element={<Link to="/welcome">Back home</Link>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(currentFaviconHref()).toBe(PUBLIC_FAVICON_HREF);

    await user.click(screen.getByRole("link", { name: "Open product" }));
    expect(currentFaviconHref()).toBe(PRODUCT_FAVICON_HREF);
  });
});
