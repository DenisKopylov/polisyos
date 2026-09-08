import { spawnSync } from "node:child_process";

import { describe, expect, it } from "vitest";

import { parsePersistenceProcessResult } from "./persistenceProcessResult";

function runChild(program: string) {
  return spawnSync(process.execPath, ["-e", program], { encoding: "utf8" });
}

describe("Atlas persistence child diagnostics", () => {
  it.each(["", "{not-json"])(
    "preserves the actual failed-child cause for stdout %j",
    (stdout) => {
      const result = runChild(
        `process.stderr.write("ModuleNotFoundError: No module named 'jsonschema'");` +
          `process.stdout.write(${JSON.stringify(stdout)});process.exit(1);`,
      );

      expect(() => parsePersistenceProcessResult(result)).toThrow(
        /exit=1.*\n.*ModuleNotFoundError: No module named 'jsonschema'/u,
      );
    },
  );

  it("names the process launch error instead of parsing absent stdout", () => {
    const result = spawnSync("/nonexistent/atlas-python", [], {
      encoding: "utf8",
    });

    expect(() => parsePersistenceProcessResult(result)).toThrow(/ENOENT/u);
  });

  it("preserves a deliberately refused JSON envelope and its nonzero status", () => {
    const result = runChild(
      'process.stdout.write(JSON.stringify({ok:false,error:{code:"intake_field_rejected"}}));process.exit(1);',
    );

    expect(parsePersistenceProcessResult(result)).toEqual({
      status: 1,
      stderr: "",
      value: { ok: false, error: { code: "intake_field_rejected" } },
    });
  });

  it("returns the completed child payload for the caller to verify", () => {
    const result = runChild("process.stdout.write(JSON.stringify({ok:true}));");

    expect(parsePersistenceProcessResult(result)).toEqual({
      status: 0,
      stderr: "",
      value: { ok: true },
    });
  });
});
