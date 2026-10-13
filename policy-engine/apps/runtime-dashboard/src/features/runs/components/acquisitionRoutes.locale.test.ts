import en from "@/shared/i18n/locales/en.json";
import uk from "@/shared/i18n/locales/uk.json";

function leafPaths(value: unknown, prefix = ""): string[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return [prefix];
  }
  return Object.entries(value).flatMap(([key, child]) =>
    leafPaths(child, prefix ? `${prefix}.${key}` : key),
  );
}

describe("DS15 acquisition surface locale contract", () => {
  it("keeps the complete English and Ukrainian acquisition key sets equal", () => {
    const english = en.pages.cycleBoard.acquisition;
    const ukrainian = uk.pages.cycleBoard.acquisition;
    const englishPaths = leafPaths(english).sort();
    const ukrainianPaths = leafPaths(ukrainian).sort();

    expect(englishPaths).toEqual(ukrainianPaths);
    expect(new Set(englishPaths).size).toBe(englishPaths.length);
    expect(Object.keys(english.backlog).length).toBe(
      englishPaths.filter((path) => path.startsWith("backlog.")).length,
    );
  });

  it("translates all three route-growth outcomes in both locales", () => {
    const english = en.pages.cycleBoard.acquisition.route;
    const ukrainian = uk.pages.cycleBoard.acquisition.route;
    expect(english.worldGrowth).toBeTruthy();
    expect(ukrainian.worldGrowth).toBeTruthy();
    expect(english.growthStatus.notEstablished).toBe("Update not established");
    expect(english.growthStatus.noGrowth).toBe(
      "No membership added to the selected active epoch",
    );
    expect(english.growthStatus.admittedDelta).toBe(
      "Membership added to the selected active epoch",
    );
    expect(ukrainian.growthStatus.notEstablished).toBeTruthy();
    expect(ukrainian.growthStatus.noGrowth).toBeTruthy();
    expect(ukrainian.growthStatus.admittedDelta).toBeTruthy();
  });

  it("names ranking authority, qualification and structural refusal in both locales", () => {
    expect(en.pages.cycleBoard.acquisition.backlog.title).toMatch(
      /ranking only, not VOI/iu,
    );
    expect(uk.pages.cycleBoard.acquisition.backlog.title).toMatch(
      /лише ranking, не VOI/iu,
    );
    for (const catalog of [en, uk]) {
      expect(
        catalog.pages.cycleBoard.acquisition.passport.epochState,
      ).toBeTruthy();
      expect(
        catalog.pages.cycleBoard.acquisition.route.structuralRefusal,
      ).toBeTruthy();
      expect(
        catalog.pages.cycleBoard.acquisition.backlog.zeroScoreBasis,
      ).toContain("0.0");
    }
  });
});
