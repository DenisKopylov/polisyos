import { spawnSync } from "node:child_process";
import process from "node:process";

const command = process.platform === "win32" ? "npx.cmd" : "npx";
const result = spawnSync(
  command,
  ["vitest", "run", "src/test/contracts/contractFixtures.test.ts"],
  {
    stdio: "inherit",
  },
);

if (typeof result.status === "number") {
  process.exitCode = result.status;
} else {
  process.exitCode = 1;
}
