import type { SpawnSyncReturns } from "node:child_process";

export type PersistenceProcessResult = Readonly<{
  status: number | null;
  stderr: string;
  value: unknown;
}>;

/** Decode the adapter's JSON envelope without masking a failed child process. */
export function parsePersistenceProcessResult(
  result: Pick<
    SpawnSyncReturns<string>,
    "error" | "signal" | "status" | "stderr" | "stdout"
  >,
): PersistenceProcessResult {
  const diagnostic =
    `Atlas persistence child failed (exit=${String(result.status)}, ` +
    `signal=${String(result.signal)}): ${result.error?.message ?? ""}\n` +
    `stderr: ${result.stderr ?? ""}`;
  if (result.error || result.signal || !result.stdout) {
    throw new Error(diagnostic, { cause: result.error });
  }
  let value: unknown;
  try {
    value = JSON.parse(result.stdout) as unknown;
  } catch (cause) {
    throw new Error(`${diagnostic}\nstdout is not valid JSON`, { cause });
  }
  // A deliberate refusal has a JSON envelope and a nonzero status. Preserve both
  // so callers assert the refusal's cause rather than treating any red as proof.
  return { status: result.status, stderr: result.stderr, value };
}
