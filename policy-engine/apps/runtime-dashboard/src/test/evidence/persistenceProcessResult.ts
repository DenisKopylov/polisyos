import type { SpawnSyncReturns } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Select this checkout’s provisioned interpreter without ambient PATH fallback. */
export function repositoryPythonExecutable(): string {
  return path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../../../../.venv/bin/python",
  );
}

// These fixtures execute independent producer/admission replays and Core CAS
// verification. The measured 127-second complete run plus 25% headroom rounds
// up to three minutes. These are liveness watchdogs, not latency assertions.
// The child must expire before the enclosing test so its cause survives.
export const PERSISTENCE_CHILD_TIMEOUT_MS = 180_000;
export const PERSISTENCE_TEST_TIMEOUT_MS =
  PERSISTENCE_CHILD_TIMEOUT_MS + 60_000;

/** Report the bounded fixture scope while reusing its existing liveness budget. */
export function evidenceFixtureWatchdog(): Readonly<{ timeout: number }> {
  console.warn(
    "Evidence fixture watchdog measures completion of the named suite's assertions. Not measured: production latency, paths outside this suite, or hosted CI. A watchdog timeout is UNRUN for the unfinished fixture, not a completed semantic verdict.",
  );
  return { timeout: PERSISTENCE_TEST_TIMEOUT_MS };
}

export type PersistenceProcessResult = Readonly<{
  status: number | null;
  stderr: string;
  value: unknown;
}>;

/** Identify unavailable execution separately from a completed semantic refusal. */
export class PersistenceExecutionUnrunError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(`UNRUN: ${message}`, options);
    this.name = "PersistenceExecutionUnrunError";
  }
}

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
    throw new PersistenceExecutionUnrunError(diagnostic, {
      cause: result.error,
    });
  }
  let value: unknown;
  try {
    value = JSON.parse(result.stdout) as unknown;
  } catch (cause) {
    throw new PersistenceExecutionUnrunError(
      `${diagnostic}\nstdout is not valid JSON`,
      { cause },
    );
  }
  // A deliberate refusal has a JSON envelope and a nonzero status. Preserve both
  // so callers assert the refusal's cause rather than treating any red as proof.
  return { status: result.status, stderr: result.stderr, value };
}
