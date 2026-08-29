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
