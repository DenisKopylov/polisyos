import { spawnSync } from "node:child_process";
import process from "node:process";

function run(command, args) {
  return spawnSync(command, args, {
    stdio: "inherit",
  });
}

const pnpmCommand = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
let result = run(pnpmCommand, [
  "exec",
  "vitest",
  "run",
  "src/test/contracts/contractFixtures.test.ts",
]);

if (result.error?.code === "ENOENT") {
  result = run("corepack", [
    "pnpm",
    "exec",
    "vitest",
    "run",
    "src/test/contracts/contractFixtures.test.ts",
  ]);
}

if (typeof result.status === "number") {
  process.exitCode = result.status;
} else {
  process.exitCode = 1;
}
