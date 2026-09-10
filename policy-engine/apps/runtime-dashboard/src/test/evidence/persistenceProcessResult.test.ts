import { spawnSync } from "node:child_process";
import {
  chmodSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { describe, expect, it } from "vitest";

import { parsePersistenceProcessResult } from "./persistenceProcessResult";
import * as persistenceProcess from "./persistenceProcessResult";

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
        /^UNRUN:.*exit=1.*\n.*ModuleNotFoundError: No module named 'jsonschema'/u,
      );
    },
  );

  it("names the process launch error instead of parsing absent stdout", () => {
    const result = spawnSync("/nonexistent/atlas-python", [], {
      encoding: "utf8",
    });

    expect(() => parsePersistenceProcessResult(result)).toThrow(
      /^UNRUN:.*ENOENT/u,
    );
  });

  it("identifies a timed-out real child as an unrun measurement", () => {
    const result = spawnSync(
      process.execPath,
      ["-e", "setTimeout(() => {}, 10000)"],
      {
        encoding: "utf8",
        timeout: 50,
      },
    );

    expect(() => parsePersistenceProcessResult(result)).toThrow(
      /^UNRUN:.*ETIMEDOUT/u,
    );
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

describe("repository Python execution binding", () => {
  it("executes provisioned Python despite a poisoned PATH from either working directory", () => {
    const productRoot = path.resolve(process.cwd(), "../..");
    const scratchRoot = path.join(productRoot, "_cache/python-launch-probes");
    mkdirSync(scratchRoot, { recursive: true });
    const scratch = mkdtempSync(path.join(scratchRoot, "path-"));
    const marker = path.join(scratch, "ambient-python-used");
    const poison = path.join(scratch, "python3");
    writeFileSync(poison, '#!/bin/sh\n: > "$PYTHON_POISON_MARKER"\nexit 73\n');
    chmodSync(poison, 0o755);
    try {
      for (const cwd of [process.cwd(), productRoot]) {
        const result = spawnSync(
          persistenceProcess.repositoryPythonExecutable(),
          [
            "-I",
            "-c",
            "import json, sys, jsonschema; print(json.dumps({'prefix': sys.prefix}))",
          ],
          {
            cwd,
            env: {
              ...process.env,
              PATH: `${scratch}${path.delimiter}${process.env.PATH ?? ""}`,
              PYTHON_POISON_MARKER: marker,
            },
            encoding: "utf8",
          },
        );
        expect(parsePersistenceProcessResult(result)).toEqual({
          status: 0,
          stderr: "",
          value: { prefix: path.join(productRoot, ".venv") },
        });
      }
      expect(existsSync(marker)).toBe(false);
    } finally {
      rmSync(scratch, { recursive: true, force: true });
    }
  });

  it("reports UNRUN when the selected checkout lacks its interpreter instead of falling back", () => {
    const scratchRoot = path.resolve(
      process.cwd(),
      "../../_cache/python-launch-probes",
    );
    mkdirSync(scratchRoot, { recursive: true });
    const scratch = mkdtempSync(path.join(scratchRoot, "missing-"));
    const fixture = path.join(
      scratch,
      "apps/runtime-dashboard/src/test/evidence/persistenceProcessResult.ts",
    );
    mkdirSync(path.dirname(fixture), { recursive: true });
    writeFileSync(
      fixture,
      readFileSync(
        path.join(
          path.dirname(fileURLToPath(import.meta.url)),
          "persistenceProcessResult.ts",
        ),
      ),
    );
    try {
      const result = spawnSync(
        process.execPath,
        [
          "--experimental-strip-types",
          "--input-type=module",
          "-e",
          `import {spawnSync} from 'node:child_process';\n` +
            `import {repositoryPythonExecutable, parsePersistenceProcessResult} from ${JSON.stringify(pathToFileURL(fixture).href)};\n` +
            `parsePersistenceProcessResult(spawnSync(repositoryPythonExecutable(), ['-c', 'print("ambient execution must not happen")'], {encoding:'utf8'}));`,
        ],
        { cwd: process.cwd(), encoding: "utf8" },
      );
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain("UNRUN:");
      expect(result.stderr).toContain("ENOENT");
      expect(result.stderr).toContain(path.join(scratch, ".venv/bin/python"));
      expect(result.stdout).toBe("");
    } finally {
      rmSync(scratch, { recursive: true, force: true });
    }
  });
});
