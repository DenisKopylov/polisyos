import { formatStatus } from "./format-status";
import {
  formatTemporalScopeForCli,
  truncateAuditHash,
  type CliTemporalScope,
  type CliTrustStatus,
} from "./tokens";

export type CliProvenanceSummary = {
  hash?: string | null;
  method?: string | null;
  source?: string | null;
  status: CliTrustStatus;
  temporalScope?: CliTemporalScope | null;
  unit?: string | null;
  valueLabel?: string | null;
  verificationNote?: string | null;
  verifiedAt?: string | null;
  verifiedBy?: string | null;
};

export function formatProvenance(summary: CliProvenanceSummary) {
  const lines = [
    `provenance ${formatStatus(summary.status)} ${truncateAuditHash(summary.hash)}`,
    summary.valueLabel
      ? `value      ${summary.valueLabel}${summary.unit ? ` (${summary.unit})` : ""}`
      : null,
    summary.source ? `source     ${summary.source}` : null,
    summary.method ? `method     ${summary.method}` : null,
    summary.verifiedBy || summary.verifiedAt
      ? `verified  ${summary.verifiedBy ?? "unknown"} at ${summary.verifiedAt ?? "unknown"}`
      : null,
    `time       ${formatTemporalScopeForCli(summary.temporalScope)}`,
    summary.verificationNote ? `note       ${summary.verificationNote}` : null,
  ].filter(Boolean);

  return lines.join("\n");
}
