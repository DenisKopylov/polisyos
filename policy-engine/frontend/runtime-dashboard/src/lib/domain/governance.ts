import { asArray, asNumber, asRecord, asString, toDisplayLabel } from "../parsing";

export type GovernanceIssueSeverity = "blocker" | "warning" | "info" | "unknown";

export type GovernanceIssueView = {
  code: string;
  message: string;
  severity: GovernanceIssueSeverity;
  passId: string | null;
  path: string | null;
  durationMs: number | null;
  raw: Record<string, unknown>;
};

export type GovernanceSummary = {
  blocker: number;
  warning: number;
  info: number;
  unknown: number;
};

function normalizeSeverity(value: string | null): GovernanceIssueSeverity {
  const normalized = (value ?? "").trim().toLowerCase();
  if (normalized === "blocker" || normalized === "error" || normalized === "fail") {
    return "blocker";
  }
  if (normalized === "warning" || normalized === "warn") {
    return "warning";
  }
  if (normalized === "info" || normalized === "notice") {
    return "info";
  }
  return "unknown";
}

function readPath(issue: Record<string, unknown>): string | null {
  const directPath = asString(issue.path);
  if (directPath) {
    return directPath;
  }

  const pathArray = asArray(issue.path);
  if (pathArray.length > 0) {
    const path = pathArray
      .map((part) => asString(part) ?? String(part))
      .filter((part) => part.length > 0)
      .join(".");
    return path.length > 0 ? path : null;
  }

  return null;
}

export function normalizeGovernanceIssues(value: unknown): GovernanceIssueView[] {
  return asArray(value)
    .map((item, index) => {
      const issue = asRecord(item);
      if (!issue) {
        return null;
      }

      const code = asString(issue.code) ?? asString(issue.issue_code) ?? `issue_${index + 1}`;
      const message =
        asString(issue.message)
        ?? asString(issue.msg)
        ?? asString(issue.description)
        ?? toDisplayLabel(code);
      const severity = normalizeSeverity(
        asString(issue.severity) ?? asString(issue.level) ?? asString(issue.type),
      );

      const passId =
        asString(issue.pass_id)
        ?? asString(issue.check_id)
        ?? asString(issue.stage)
        ?? asString(issue.scope);

      return {
        code,
        message,
        severity,
        passId,
        path: readPath(issue),
        durationMs: asNumber(issue.duration_ms),
        raw: issue,
      };
    })
    .filter((item): item is GovernanceIssueView => item !== null);
}

export function summarizeGovernanceIssues(issues: GovernanceIssueView[]): GovernanceSummary {
  return issues.reduce<GovernanceSummary>(
    (acc, issue) => {
      acc[issue.severity] += 1;
      return acc;
    },
    {
      blocker: 0,
      warning: 0,
      info: 0,
      unknown: 0,
    },
  );
}
