import { render, screen } from "@testing-library/react";

const { createBrowserRouterMock, routerProviderMock } = vi.hoisted(() => ({
  createBrowserRouterMock: vi.fn((routes: unknown) => ({
    id: "app-router",
    routes,
  })),
  routerProviderMock: vi.fn(({ router }: { router: { id: string } }) => (
    <div data-testid="router-provider">{router.id}</div>
  )),
}));

const APP_ROUTES_MOCK = [{ path: "/" }];

vi.mock("react-router-dom", () => ({
  RouterProvider: (props: { router: { id: string } }) =>
    routerProviderMock(props),
  createBrowserRouter: (routes: unknown) => createBrowserRouterMock(routes),
}));

describe("AppRouter", () => {
  beforeEach(() => {
    routerProviderMock.mockClear();
  });

  it("creates the browser router from APP_ROUTES and renders RouterProvider", async () => {
    vi.resetModules();
    createBrowserRouterMock.mockClear();

    vi.doMock("@/app/routes/routes", () => ({
      APP_ROUTES: APP_ROUTES_MOCK,
    }));

    const { AppRouter } = await import("@/app/routes/AppRouter");

    render(<AppRouter />);

    expect(createBrowserRouterMock).toHaveBeenCalledWith(APP_ROUTES_MOCK);
    expect(routerProviderMock).toHaveBeenCalledWith(
      expect.objectContaining({
        router: expect.objectContaining({ id: "app-router" }),
      }),
    );
    expect(screen.getByTestId("router-provider")).toHaveTextContent(
      "app-router",
    );
  });
});
