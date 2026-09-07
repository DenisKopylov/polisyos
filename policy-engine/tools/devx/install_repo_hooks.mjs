/** Install shared hooks whose runtime belongs to the checkout making the Git operation. */
import { execFileSync } from "node:child_process";
import {
  chmodSync,
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repository = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
const hooks = execFileSync(
  "git",
  ["rev-parse", "--path-format=absolute", "--git-path", "hooks"],
  { cwd: repository, encoding: "utf8" },
).trim();
const marker = "# PolicyOS checkout-local Lefthook dispatcher.";

// No installing checkout path is interpolated into these shared bytes.
const dispatcher = `#!/bin/sh
${marker}
set -eu
root="$(git rev-parse --show-toplevel)" || exit 1
config="$root/policy-engine/apps/runtime-dashboard/lefthook.yml"
binary="$root/policy-engine/apps/runtime-dashboard/node_modules/.bin/lefthook"
if [ ! -f "$config" ] || [ ! -r "$config" ]; then
  echo "PolicyOS hook: missing config: $config" >&2
  exit 1
fi
if [ ! -f "$binary" ] || [ ! -x "$binary" ]; then
  echo "PolicyOS hook: missing binary: $binary; run corepack pnpm install --frozen-lockfile in policy-engine." >&2
  exit 1
fi
export LEFTHOOK_CONFIG="$config"
cd "$root"
exec "$binary" run "$(basename "$0")" --no-auto-install "$@"
`;

mkdirSync(hooks, { recursive: true });
for (const name of ["pre-commit", "pre-push"]) {
  const destination = path.join(hooks, name);
  if (existsSync(destination)) {
    const previous = readFileSync(destination, "utf8");
    if (previous === dispatcher) {
      chmodSync(destination, 0o755);
      continue;
    }
    // Replace generated Lefthook hooks, but never destroy an unrecognized user hook.
    if (!previous.includes(marker) && !previous.includes("call_lefthook()")) {
      const backup = `${destination}.old`;
      if (existsSync(backup)) {
        throw new Error(
          `Refusing to replace user hook ${destination}: ${backup} already exists`,
        );
      }
      renameSync(destination, backup);
    }
  }
  const temporary = `${destination}.policyos-${process.pid}`;
  writeFileSync(temporary, dispatcher, { mode: 0o755, flag: "wx" });
  renameSync(temporary, destination);
}
