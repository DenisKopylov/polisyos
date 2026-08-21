import { http, HttpResponse } from "msw";

import { loadAllRuntimeContractFixtures } from "@/test/contracts/runtimeContractFixtures";

const fixtureHandlers = loadAllRuntimeContractFixtures().map((fixture) => {
  const resolver = () => HttpResponse.json(fixture.payload);

  switch (fixture.method) {
    case "GET":
      return http.get(fixture.mswPath, resolver);
    case "POST":
      return http.post(fixture.mswPath, resolver);
  }
});

// DS16-C05: the authority-values endpoint answers with a complete-but-empty projection
// by default, so consumers that mount a panel incidentally do not fail on an unhandled
// request. Tests that care about the payload override this with `server.use`.
const authorityValuesHandler = http.get(
  "*/api/v1/runs/:runId/authority-values",
  ({ params }) =>
    HttpResponse.json({
      inventory_version: "ds16-c05.1",
      retirement_commit: "bc1d01001",
      run_id: String(params.runId),
      values: [],
    }),
);

export const handlers = [...fixtureHandlers, authorityValuesHandler];
