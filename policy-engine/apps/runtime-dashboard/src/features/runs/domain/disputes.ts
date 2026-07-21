import type { GovernanceIssueView } from "@/shared/lib/domain/governance";
import {
  createInteractionState,
  type InteractionState,
} from "@/shared/lib/domain/statusOwnership";

export type DisputeRecord = {
  actor: "governance" | "reviewer";
  basis: string;
  id: string;
  openedAt: string;
  status: InteractionState;
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
    status: createDisputeStatus(
      issue.severity === "blocker" ? "open" : "under_review",
    ),
    target: issue.path ?? issue.passId ?? "decision",
    title: issue.message,
  };
}

export function disputeStorageKey(runId: string) {
  return `polisyos:atlas:disputes:${runId}`;
}

export function createDisputeStatus(value: unknown): InteractionState {
  const label =
    typeof value === "string"
      ? value
      : typeof value === "object" &&
          value !== null &&
          "label" in value &&
          typeof value.label === "string"
        ? value.label
        : null;
  if (
    label !== "open" &&
    label !== "under_review" &&
    label !== "resolved"
  ) {
    throw new TypeError("run dispute interaction state is unrecognized");
  }
  return createInteractionState(label, "progress");
}

function parseDisputeRecord(value: unknown): DisputeRecord | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const structurallyValid =
    (record.actor === "governance" || record.actor === "reviewer") &&
    typeof record.basis === "string" &&
    typeof record.id === "string" &&
    typeof record.openedAt === "string" &&
    typeof record.target === "string" &&
    typeof record.title === "string";
  if (!structurallyValid) {
    return null;
  }
  try {
    return {
      actor: record.actor as DisputeRecord["actor"],
      basis: record.basis as string,
      id: record.id as string,
      openedAt: record.openedAt as string,
      status: createDisputeStatus(record.status),
      target: record.target as string,
      title: record.title as string,
    };
  } catch {
    return null;
  }
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
      ? parsed.disputes
          .map(parseDisputeRecord)
          .filter((record): record is DisputeRecord => record !== null)
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
        disputes: disputes.map(({ status, ...dispute }) => ({
          ...dispute,
          status: status.label,
        })),
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
