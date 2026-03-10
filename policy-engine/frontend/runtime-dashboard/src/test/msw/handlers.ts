import { http, HttpResponse } from "msw";

import {
  loadAllRuntimeContractFixtures,
} from "@/test/contracts/runtimeContractFixtures";

const fixtureHandlers = loadAllRuntimeContractFixtures().map((fixture) => {
  const resolver = () => HttpResponse.json(fixture.payload);

  switch (fixture.method) {
    case "GET":
      return http.get(fixture.mswPath, resolver);
    case "POST":
      return http.post(fixture.mswPath, resolver);
  }
});

export const handlers = [...fixtureHandlers];
