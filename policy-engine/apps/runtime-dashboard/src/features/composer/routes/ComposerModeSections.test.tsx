import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const sourcePath = resolve(
  process.cwd(),
  "src/features/composer/routes/ComposerModeSections.tsx",
);

describe("ComposerModeSections", () => {
  it("does not accept a discovery capability projection from its parent", () => {
    expect(readFileSync(sourcePath, "utf8")).not.toContain(
      "capabilityHighlights",
    );
  });
});
