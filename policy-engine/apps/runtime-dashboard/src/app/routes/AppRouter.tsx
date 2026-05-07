import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { APP_ROUTES } from "@/app/routes/routes";

const appRouter = createBrowserRouter(APP_ROUTES);

export function AppRouter() {
  return <RouterProvider router={appRouter} />;
}
