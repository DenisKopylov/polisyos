import {
  chmodSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";

import { describe, expect, it, vi } from "vitest";

import { measureAtlasHealthMetrics } from "./atlasHealthMetrics";
import { buildAtlasStableReadinessNegativeControl } from "./atlasSurfaceReadinessReconciliation";
import { repositoryPythonExecutable } from "./persistenceProcessResult";

describe("evidence producer unavailable execution", () => {
  it.each(
    [
      measureAtlasHealthMetrics,
      buildAtlasStableReadinessNegativeControl,
    ].flatMap((produce) =>
      ["missing interpreter", "missing dependency", "invalid JSON"].map(
        (condition) => ({ produce, condition }),
      ),
    ),
  )(
    "reports UNRUN for $condition in $produce.name",
    ({ condition, produce }) => {
      const scratchRoot = path.resolve(
        process.cwd(),
        "../../_cache/python-launch-probes",
      );
      mkdirSync(scratchRoot, { recursive: true });
      const root = mkdtempSync(path.join(scratchRoot, "producer-"));
      const dashboard = path.join(root, "apps/runtime-dashboard");
      mkdirSync(path.join(dashboard, "scripts"), { recursive: true });
      writeFileSync(
        path.join(dashboard, "scripts/validate_atlas_health_sources.py"),
        "import jsonschema\n",
      );
      if (condition !== "missing interpreter") {
        const python = path.join(root, ".venv/bin/python");
        mkdirSync(path.dirname(python), { recursive: true });
        writeFileSync(
          python,
          condition === "invalid JSON"
            ? "#!/bin/sh\nprintf '{invalid-json'\n"
            : `#!/bin/sh\nexec '${repositoryPythonExecutable().replaceAll("'", "'\\''")}' -S "$@"\n`,
        );
        chmodSync(python, 0o755);
      }
      const cwd = vi.spyOn(process, "cwd").mockReturnValue(dashboard);
      try {
        expect(produce).toThrow(/^UNRUN:/u);
        expect(produce).toThrow(
          condition === "missing dependency"
            ? /No module named 'jsonschema'/u
            : /^UNRUN:/u,
        );
      } finally {
        cwd.mockRestore();
        rmSync(root, { recursive: true, force: true });
      }
    },
  );
});
