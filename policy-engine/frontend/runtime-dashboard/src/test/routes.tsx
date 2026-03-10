import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes, type RouteObject } from "react-router-dom";

import { createAppRenderHarness } from "@/test/render";

type RenderRouteOptions = {
  element: ReactElement;
  path: string;
  initialEntry?: string;
  extraRoutes?: RouteObject[];
};

export function renderRouteWithProviders({
  element,
  path,
  initialEntry = path,
  extraRoutes = [],
}: RenderRouteOptions) {
  const { queryClient, baseWrapper: AppProviders } = createAppRenderHarness();

  return {
    queryClient,
    ...render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <AppProviders>
          <Routes>
            <Route path={path} element={element} />
            {extraRoutes.map((route) => (
              <Route
                key={`${route.path ?? "index"}-${String(route.index ?? false)}`}
                path={route.path}
                element={route.element}
              />
            ))}
          </Routes>
        </AppProviders>
      </MemoryRouter>,
    ),
  };
}
