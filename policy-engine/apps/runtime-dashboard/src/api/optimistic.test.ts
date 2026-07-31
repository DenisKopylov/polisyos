import * as optimisticRunCache from "@/api/optimistic";

describe("optimistic run cache", () => {
  it("does not fabricate RunSummary records for launch interaction state", () => {
    expect(Object.keys(optimisticRunCache)).not.toEqual(
      expect.arrayContaining([
        "applyOptimisticRunToCache",
        "buildLaunchedRunSummary",
        "createOptimisticRun",
        "createOptimisticRunDetails",
        "replaceOptimisticRunInCache",
      ]),
    );
  });
});
