import type { RouteObject } from "react-router-dom";

import RunComparePage from "@/features/runs/routes/RunComparePage";

export const policyDiffRoute = {
  path: "compare/:runA/:runB",
  element: <RunComparePage />,
} satisfies RouteObject;
