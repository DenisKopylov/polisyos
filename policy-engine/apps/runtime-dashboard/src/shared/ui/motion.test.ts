import { motionDurations } from "@polisyos/atlas-ui";

import { duration, easing } from "./motion";

describe("motion token projection", () => {
  it("consumes generated helper durations without changing Motion seconds", () => {
    expect(duration).toEqual({
      emphasis: motionDurations.helper.emphasisMs / 1000,
      fast: motionDurations.helper.fastMs / 1000,
      moderate: motionDurations.helper.moderateMs / 1000,
      slow: motionDurations.helper.slowMs / 1000,
    });
    expect(easing.standard).toEqual([0.2, 0, 0, 1]);
    expect(easing.decelerate).toEqual([0, 0, 0, 1]);
    expect(easing.accelerate).toEqual([0.3, 0, 1, 1]);
  });
});
