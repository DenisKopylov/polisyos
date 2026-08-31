import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(import.meta.url);
const fixedEnvironment = {
  HOME: "/var/empty",
  LANG: "C",
  LC_ALL: "C",
  PATH: "/usr/bin:/bin",
  TZ: "UTC",
};

if (process.argv.length !== 2) {
  process.stderr.write("DS18 outcome runner accepts no caller-supplied arguments\n");
  process.exitCode = 1;
} else if (!process.execArgv.includes("--experimental-strip-types")) {
  const relaunched = spawnSync(
    process.execPath,
    ["--experimental-strip-types", scriptPath],
    { encoding: "utf8", env: fixedEnvironment },
  );
  process.stdout.write(relaunched.stdout ?? "");
  process.stderr.write(relaunched.stderr ?? "");
  process.exitCode = relaunched.status ?? 1;
} else {
  const dashboardRoot = fileURLToPath(new URL("..", import.meta.url));
  const policyEngineRoot = path.resolve(dashboardRoot, "../..");
  const repositoryPython = path.join(policyEngineRoot, ".venv/bin/python");
  const canonicalChecker = path.join(
    policyEngineRoot,
    "architecture/atlas_surfaces/check_frontend_disposition_register.py",
  );
  const outcomeModule = await import("../src/test/evidence/ds18ExecutionOutcome.ts");

  if (!existsSync(repositoryPython)) {
    process.stderr.write(
      "DS18 outcome runner requires its repository-managed checker\n",
    );
    process.exitCode = 1;
  } else {
    const checker = spawnSync(
      repositoryPython,
      ["-I", canonicalChecker, "--check-ds18-time-semantics-coverage"],
      {
        cwd: policyEngineRoot,
        env: {
          ...fixedEnvironment,
          POLISYOS_NODE_EXECUTABLE: process.execPath,
        },
        maxBuffer: 2 * (outcomeModule.DS18_MAX_STREAM_BYTES + 1),
      },
    );
    const outcome = outcomeModule.decodeDs18ExecutionOutcome({
      exitCode: checker.status ?? 1,
      stdout: checker.stdout ?? Buffer.alloc(0),
      stderr: checker.stderr ?? Buffer.alloc(0),
    });
    process.stdout.write(`${JSON.stringify(outcome)}\n`);
  }
}
