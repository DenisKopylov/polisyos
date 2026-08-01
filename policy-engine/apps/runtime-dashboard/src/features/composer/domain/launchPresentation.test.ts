import type { RunLaunchResponse } from "@polisyos/runtime-api-client";
import type { BadgeTone } from "@polisyos/atlas-ui";
import type { launchStatusTone as LaunchStatusTone } from "./launchPresentation";

describe("launch presentation", () => {
  it("uses the single owner-bound launch presentation adapter", async () => {
    const modulePath = "./launchPresentation";
    const { launchStatusTone } = await import(/* @vite-ignore */ modulePath);

    expectTypeOf<typeof LaunchStatusTone>()
      .parameter(0)
      .toEqualTypeOf<RunLaunchResponse["status"]>();
    expectTypeOf<typeof LaunchStatusTone>().returns.toEqualTypeOf<BadgeTone>();
    expect(launchStatusTone("accepted")).toBe("ok");
    expect(launchStatusTone("rejected")).toBe("fail");
  });
});
