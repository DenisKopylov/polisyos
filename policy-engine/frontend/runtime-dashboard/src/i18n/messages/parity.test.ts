import en from "./en";
import uk from "./uk";

function collectPaths(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value == null || Array.isArray(value)) {
    return prefix ? [prefix] : [];
  }

  return Object.entries(value as Record<string, unknown>).flatMap(
    ([key, nested]) => collectPaths(nested, prefix ? `${prefix}.${key}` : key),
  );
}

describe("locale catalogs", () => {
  it("keep English and Ukrainian message keys in sync", () => {
    const enKeys = collectPaths(en).sort();
    const ukKeys = collectPaths(uk).sort();

    expect(ukKeys).toEqual(enKeys);
  });
});
