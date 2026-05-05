import type { GovernanceIssueView } from "@/shared/lib/domain/governance";

export type DisputeStatus = "open" | "under_review" | "resolved";

export type DisputeRecord = {
  actor: "governance" | "reviewer";
  basis: string;
  id: string;
  openedAt: string;
  status: DisputeStatus;
  target: string;
  title: string;
};

export const DISPUTES_CHANGED_EVENT = "polisyos:atlas:disputes-changed";

export function issueToDispute(issue: GovernanceIssueView): DisputeRecord {
  const raw = issue.raw ?? {};
  const openedAt =
    typeof raw.timestamp === "string"
      ? raw.timestamp
      : typeof raw.created_at === "string"
        ? raw.created_at
        : "1970-01-01T00:00:00.000Z";
  return {
    actor: "governance",
    basis: issue.passId ?? issue.code,
    id: `issue:${issue.code}`,
    openedAt,
    status: issue.severity === "blocker" ? "open" : "under_review",
    target: issue.path ?? issue.passId ?? "decision",
    title: issue.message,
  };
}

export function disputeStorageKey(runId: string) {
  return `polisyos:atlas:disputes:${runId}`;
}

export function isDisputeRecord(value: unknown): value is DisputeRecord {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Partial<DisputeRecord>;
  return (
    (record.actor === "governance" || record.actor === "reviewer") &&
    typeof record.basis === "string" &&
    typeof record.id === "string" &&
    typeof record.openedAt === "string" &&
    (record.status === "open" ||
      record.status === "under_review" ||
      record.status === "resolved") &&
    typeof record.target === "string" &&
    typeof record.title === "string"
  );
}

export function readStoredDisputes(runId: string): DisputeRecord[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(disputeStorageKey(runId));
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as { disputes?: unknown };
    return Array.isArray(parsed.disputes)
      ? parsed.disputes.filter(isDisputeRecord)
      : [];
  } catch {
    return [];
  }
}

export function writeStoredDisputes(runId: string, disputes: DisputeRecord[]) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(
      disputeStorageKey(runId),
      JSON.stringify({
        disputes,
        savedAt: new Date().toISOString(),
        version: 1,
      }),
    );
    window.dispatchEvent(
      new CustomEvent(DISPUTES_CHANGED_EVENT, {
        detail: { runId },
      }),
    );
  } catch {
    // Local dispute persistence is best-effort until the registry has a write API.
  }
}

export function buildDisputeRecords(
  issues: GovernanceIssueView[],
  localDisputes: DisputeRecord[],
) {
  return [...localDisputes, ...issues.map(issueToDispute)];
}
