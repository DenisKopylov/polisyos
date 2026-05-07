import { loadAllRuntimeContractFixtures } from "./runtimeContractFixtures";

describe("runtime contract fixtures", () => {
  it("parse every recorded fixture with the frontend runtime schemas", () => {
    for (const fixture of loadAllRuntimeContractFixtures()) {
      expect(() => fixture.schema.parse(fixture.payload)).not.toThrow();
    }
  });
});
