export type CliTrustStatus =
  | "verified"
  | "pending"
  | "stale"
  | "disputed"
  | "untraced";

export type CliSeverity =
  | "trace"
  | "debug"
  | "info"
  | "success"
  | "warning"
  | "error"
  | "fatal";

export type CliProgressState =
  | "queued"
  | "running"
  | "blocked"
  | "complete"
  | "failed";

export const CLI_STATUS_TOKENS: Record<CliTrustStatus, string> = {
  disputed: "[DISPUTED]",
  pending: "[PENDING]",
  stale: "[STALE]",
  untraced: "[UNTRACED]",
  verified: "[VERIFIED]",
};

export const CLI_SEVERITY_TOKENS: Record<CliSeverity, string> = {
  debug: "DBG",
  error: "ERR",
  fatal: "FTL",
  info: "INF",
  success: "OK",
  trace: "TRC",
  warning: "WRN",
};

export const CLI_PROGRESS_TOKENS: Record<CliProgressState, string> = {
  blocked: "BLOCKED",
  complete: "DONE",
  failed: "FAILED",
  queued: "QUEUED",
  running: "RUNNING",
};

export const CLI_STATUS_DESCRIPTIONS: Record<CliTrustStatus, string> = {
  disputed: "Lineage or source has an active dispute.",
  pending: "Lineage exists but verification has not completed.",
  stale: "Verified earlier, but newer evidence or model output exists.",
  untraced: "No trustworthy lineage is attached yet.",
  verified: "Lineage and hash verification completed for this temporal scope.",
};

export type CliTemporalScope = {
  branch?: string | null;
  scenarioId?: string | null;
  txAt?: string | null;
  validAt?: string | null;
};

export function formatTemporalScopeForCli(scope?: CliTemporalScope | null) {
  if (!scope) {
    return "valid=latest tx=latest";
  }

  const parts = [
    `valid=${scope.validAt ?? "latest"}`,
    `tx=${scope.txAt ?? "latest"}`,
    scope.branch ? `branch=${scope.branch}` : null,
    scope.scenarioId ? `scenario=${scope.scenarioId}` : null,
  ].filter(Boolean);

  return parts.join(" ");
}

export function truncateAuditHash(hash?: string | null, size = 10) {
  if (!hash) {
    return "hash=missing";
  }

  const [algorithm, digest = algorithm] = hash.includes(":")
    ? hash.split(":", 2)
    : ["sha256", hash];
  const visibleDigest =
    digest.length > size ? `${digest.slice(0, size)}...` : digest;

  return `${algorithm}:${visibleDigest}`;
}
