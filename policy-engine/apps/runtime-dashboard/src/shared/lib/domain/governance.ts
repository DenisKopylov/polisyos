import {
  asArray,
  asNumber,
  asRecord,
  asString,
  toDisplayLabel,
} from "../parsing";

export type GovernanceIssueView = {
  code: string;
  message: string;
  severity: string | null;
  passId: string | null;
  path: string | null;
  durationMs: number | null;
  raw: Record<string, unknown>;
};

export type GovernanceSummary = {
  byOwnerLabel: Record<string, number>;
  total: number;
  unlabeled: number;
};

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

export function normalizeGovernanceIssues(
  value: unknown,
): GovernanceIssueView[] {
  return asArray(value)
    .map((item, index) => {
      const issue = asRecord(item);
      if (!issue) {
        return null;
      }

      const code =
        asString(issue.code) ??
        asString(issue.issue_code) ??
        `issue_${index + 1}`;
      const message =
        asString(issue.message) ??
        asString(issue.msg) ??
        asString(issue.description) ??
        toDisplayLabel(code);
      const severity =
        asString(issue.severity) ??
        asString(issue.level) ??
        asString(issue.type);

      const passId =
        asString(issue.pass_id) ??
        asString(issue.check_id) ??
        asString(issue.stage) ??
        asString(issue.scope);

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

export function summarizeGovernanceIssues(
  issues: GovernanceIssueView[],
): GovernanceSummary {
  const byOwnerLabel: Record<string, number> = {};
  let unlabeled = 0;
  for (const issue of issues) {
    if (issue.severity === null) {
      unlabeled += 1;
      continue;
    }
    byOwnerLabel[issue.severity] = (byOwnerLabel[issue.severity] ?? 0) + 1;
  }
  return { byOwnerLabel, total: issues.length, unlabeled };
}
