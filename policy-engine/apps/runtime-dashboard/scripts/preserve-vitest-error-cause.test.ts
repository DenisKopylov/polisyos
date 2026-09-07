import { spawnSync } from "node:child_process";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";

import { expect, it } from "vitest";

it("reports the real timeout cause and identity through the configured JSON reporter", () => {
  const dashboardRoot = process.cwd();
  const scratch = path.resolve(
    dashboardRoot,
    "../../_cache/vitest-cause-probes",
  );
  mkdirSync(scratch, { recursive: true });
  const directory = mkdtempSync(path.join(scratch, "timeout-"));
  const fixture = path.join(directory, "slow.test.ts");
  const config = path.join(directory, "vitest.config.ts");
  const report = path.join(directory, "report.json");
  const names = ["stalled asynchronous witness", "slow synchronous witness"];
  try {
    writeFileSync(
      fixture,
      `it(${JSON.stringify(names[0])}, async () => { await new Promise((resolve) => setTimeout(resolve, 50)); }, 5);\n` +
        `it(${JSON.stringify(names[1])}, () => { const stop = performance.now() + 20; while (performance.now() < stop) {} }, 5);\n`,
    );
    writeFileSync(
      config,
      `import config from ${JSON.stringify(path.join(dashboardRoot, "vitest.config.ts"))};\n` +
        `export default { ...config, test: { ...config.test, projects: undefined, include: [${JSON.stringify(fixture)}], environment: "node", setupFiles: [] } };\n`,
    );
    const result = spawnSync(
      process.execPath,
      [
        path.join(dashboardRoot, "node_modules/vitest/vitest.mjs"),
        "run",
        "--config",
        config,
        "--reporter=json",
        `--outputFile=${report}`,
        "--maxWorkers=1",
      ],
      { cwd: dashboardRoot, encoding: "utf8", timeout: 30_000 },
    );
    expect(result.error, result.stderr).toBeUndefined();
    expect(result.status, result.stderr).toBe(1);
    const value = JSON.parse(readFileSync(report, "utf8")) as {
      testResults: Array<{
        assertionResults: Array<{
          fullName: string;
          status: string;
          failureMessages: string[];
        }>;
      }>;
    };
    const cases = value.testResults.flatMap((file) => file.assertionResults);
    expect(cases.map((testCase) => testCase.fullName)).toEqual(names);
    for (const testCase of cases) {
      expect(testCase.status).toBe("failed");
      expect(testCase.failureMessages.join("\n")).toContain(
        "Test timed out in 5ms",
      );
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}, 45_000);
